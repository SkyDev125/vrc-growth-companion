"""Finite, proportional transitions; linked quantities are evaluated parent-first."""
import copy
import math
import threading
import time
import avatar_mapping as mapping


def duration(start, end):
    if start == end: return 0.
    distance = abs(math.log2(end / start)) if start > 0 and end > 0 else abs(end-start)/max(abs(start),abs(end),1.)
    return min(120., max(3., 3. + 8.*distance))


def blend(start, end, progress):
    if progress >= 1: return end
    if progress <= 0: return start
    u=progress**3*(10+progress*(-15+6*progress))
    return math.exp(math.log(start)+(math.log(end)-math.log(start))*u) if start > 0 and end > 0 else start+(end-start)*u


def links(sources):
    by_id={s['id']:s for s in sources}
    # Invalid/legacy metadata becomes an independent measurement, never a recursive loop.
    parents={k:str(s.get('syncTarget','none')) for k,s in by_id.items()}
    for key in parents:
        seen={key};current=parents[key]
        while current in parents:
            if current in seen:raise ValueError('Measurement links contain a cycle.')
            seen.add(current);current=parents[current]
    return by_id,parents


class Transition:
    def __init__(self):
        self.targets=[];self.starts={};self.ends={};self.started=0.;self.seconds=0.

    def values(self, now):
        if not self.targets:return []
        u=min(1.,max(0.,(now-self.started)/self.seconds)) if self.seconds else 1.
        by_id,parents=links(self.targets);values={}
        def evaluate(key):
            if key in values:return values[key]
            source=by_id[key];value=blend(self.starts[key],self.ends[key],u)
            parent=parents[key]
            if parent in by_id:
                value*= (evaluate(parent)/by_id[parent]['originalValue'])**int(source.get('syncPower',1))
            values[key]=value;return value
        return [{**s,'value':s['value'] if u>=1 else evaluate(s['id'])} for s in self.targets]

    def update(self, sources, now, initial_height=None, animated_ids=None):
        sources=copy.deepcopy(sources)
        try:by_id,parents=links(sources)
        except ValueError:
            sources=[{**s,'syncTarget':'none'} for s in sources];by_id,parents=links(sources)
        if sources==self.targets:return
        previous={s['id']:s for s in self.values(now)}
        if not previous and initial_height is not None:
            previous={s['id']:dict(s) for s in sources}
            if 'height' in previous:previous['height']['value']=initial_height
            resolved=set()
            def seed(key):
                if key in resolved:return previous[key]['value']
                parent=parents[key]
                if parent in by_id:
                    previous[key]['value']=by_id[key]['value']*(seed(parent)/by_id[parent]['value'])**int(by_id[key].get('syncPower',1))
                resolved.add(key);return previous[key]['value']
            for key in by_id:seed(key)
        self.starts={};self.ends={}
        for key,s in by_id.items():
            parent=parents[key];power=int(s.get('syncPower',1))
            end=s['value'];start=previous.get(key,s)['value']
            if parent in by_id and by_id[parent]['originalValue']>0:
                end/= (by_id[parent]['value']/by_id[parent]['originalValue'])**power
                old_parent=previous.get(parent,by_id[parent])
                start/= (old_parent['value']/by_id[parent]['originalValue'])**power
            self.starts[key]=start;self.ends[key]=end
        self.targets=sources;self.started=now
        relevant=set(self.ends) if animated_ids is None else set(animated_ids)
        for key in list(relevant):
            parent=parents.get(key)
            while parent in by_id:relevant.add(parent);parent=parents.get(parent)
        self.seconds=max((duration(self.starts[k],self.ends[k]) for k in relevant if k in self.ends),default=0.)

    def finish(self):self.seconds=0.
    def active(self,now):return self.seconds>0 and now<self.started+self.seconds


def wants_smoothing(item, sources, enabled):
    source=sources.get(item['source'],{})
    default=item['target']=='/avatar/eyeheight' or source.get('syncTarget','none')!='none'
    return enabled and item['kind']=='float' and item.get('smooth',default)


class MotionSender:
    """Animation runs separately from slow HTTP/OSCQuery polling; one bounded-rate worker."""
    def __init__(self, owner, stop):
        self.owner=owner;self.stop=stop;self.lock=threading.RLock();self.transition=Transition()
        self.sender=mapping.ChangedSender();self.context=None;self.config=None;self.items=[];self.discovery=None
        self.epoch=owner.motion_epoch;self.finish_generation=owner.finish_generation
        self.last_state=None;self.closed=threading.Event()
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()

    def clear(self):
        with self.lock:self.config=None;self.items=[];self.transition=Transition();self.last_state=None
        self.owner.events.put(('motion',{'active':False,'outputs':{}}))

    def submit(self, context, config, items, sources, discovery):
        now=time.monotonic()
        with self.lock:
            if context!=self.context:
                self.transition=Transition();self.context=context;self.sender.begin(context)
            self.config=config;self.items=copy.deepcopy(items);self.discovery=discovery;self.epoch=self.owner.motion_epoch
            raw={s['id']:s for s in sources}
            animated={i['source'] for i in items if i.get('enabled',True) and wants_smoothing(i,raw,config.get('smoothGrowth',False))}
            self.transition.update(sources,now,(discovery or {}).get('eyeHeight'),animated)
            self.tick(now)

    def tick(self, now):
        if self.stop.is_set() or self.config is None:return
        with self.owner.lock:
            live=copy.deepcopy(self.owner.config);epoch=self.owner.motion_epoch;finish=self.owner.finish_generation
        if epoch!=self.epoch or (live['oscHost'],live['oscPort'])!=self.context[:2]:self.clear();return
        raw={s['id']:s for s in self.transition.targets}
        if not live.get('smoothGrowth',False):self.transition.finish()
        if finish!=self.finish_generation:self.transition.finish();self.finish_generation=finish
        displayed={s['id']:s for s in self.transition.values(now)}
        items=live.get('profiles',{}).get(self.context[2],[])
        # Mapping edits, toggles and removals are effective at the next animation tick.
        valid=[i for i in self.items if i in items and i.get('enabled',True) and mapping.can_send(i,raw,self.discovery)]
        self.sender.prune({i['target'] for i in valid})
        active=False;outputs={}
        for item in valid:
            if self.stop.is_set():break
            smooth=wants_smoothing(item,raw,live.get('smoothGrowth',False))
            source=(displayed if smooth else raw)[item['source']]
            if item['target']=='/avatar/eyeheight' and (self.discovery or {}).get('scalingAllowed') is False:continue
            try:
                self.sender.send(self.config,item,source)
                outputs[item['target']]=mapping.mapped_value(item,source)
                active=active or (smooth and self.transition.active(now))
            except (OSError,ValueError,OverflowError,KeyError):continue
        state={'active':active,'outputs':outputs}
        if state!=self.last_state:self.owner.events.put(('motion',state));self.last_state=state

    def run(self):
        while not self.closed.wait(.05) and not self.stop.is_set():
            try:
                with self.lock:self.tick(time.monotonic())
            except (ValueError,KeyError,TypeError,OverflowError,OSError) as error:
                self.clear();self.owner.events.put(('status','Growth paused: '+str(error)))

    def close(self):
        # The owner sets stop before shutdown; no further writes after joining.
        self.stop.set();self.closed.set();self.thread.join(timeout=2)
