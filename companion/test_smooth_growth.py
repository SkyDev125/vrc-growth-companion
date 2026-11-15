import copy,math,queue,socket,threading,time,unittest
from unittest.mock import patch
from types import SimpleNamespace
import smooth_growth as g
import avatar_mapping as m


def sources(height,diameter=1):
    return [{'id':'height','value':height,'originalValue':1,'unit':'m','name':'Height'},
            {'id':'diameter','value':diameter*height,'originalValue':1,'unit':'m','name':'Diameter','syncTarget':'height','syncPower':1},
            {'id':'capacity','value':(diameter*height)**3,'originalValue':1,'unit':'L','name':'Capacity','syncTarget':'diameter','syncPower':3}]


class GrowthTests(unittest.TestCase):
    def test_bounded_proportional_timing_and_eased_exact_endpoint(self):
        self.assertAlmostEqual(g.duration(2,4),g.duration(200,400))
        self.assertLess(g.duration(2,2.1),g.duration(2,20))
        self.assertEqual(g.duration(.01,10000),120)
        self.assertEqual(g.blend(1,100,1),100)
        self.assertAlmostEqual(g.blend(1,100,.5),10)
        self.assertLess(g.blend(1,100,.01)-1,.01)
        self.assertEqual(g.blend(-5,5,.5),0)
        self.assertTrue(all(g.blend(10,1,i/100)>=g.blend(10,1,(i+1)/100) for i in range(100)))

    def test_linked_volume_and_direct_growth_stay_consistent_every_frame(self):
        t=g.Transition();t.update(sources(1),0);t.update(sources(2,2),1)
        for i in range(101):
            v={s['id']:s['value'] for s in t.values(1+t.seconds*i/100)}
            self.assertAlmostEqual(v['capacity'],v['diameter']**3,places=8)
        self.assertEqual(t.values(1000),sources(2,2))

    def test_retarget_continuity_finish_and_unchanged_poll_does_not_restart(self):
        t=g.Transition();t.update(sources(1),0);t.update(sources(10),1)
        before=t.values(5);t.update(sources(100),5)
        for a,b in zip(before,t.values(5)):self.assertAlmostEqual(a['value'],b['value'])
        started=t.started;t.update(sources(100),6);self.assertEqual(started,t.started)
        t.finish();self.assertFalse(t.active(6));self.assertEqual(t.values(6),sources(100))

    def test_initial_live_height_and_cubic_dependents(self):
        t=g.Transition();t.update(sources(4),0,initial_height=2)
        values={s['id']:s['value'] for s in t.values(0)}
        self.assertEqual(values['height'],2);self.assertEqual(values['capacity'],8)
        # Without an observed start there is no invented growth from zero.
        t=g.Transition();t.update(sources(4),0);self.assertFalse(t.active(0))

    def test_bad_graph_and_unrelated_attribute_do_not_break_height(self):
        t=g.Transition();a=sources(1);a.append({'id':'unused','value':1,'originalValue':1})
        t.update(a,0);b=copy.deepcopy(a);b[0]['value']=2;b[-1]['value']=1e30
        t.update(b,1,animated_ids={'height'});self.assertEqual(t.seconds,11)
        a[1]['syncTarget']='capacity';t=g.Transition();t.update(a,0)
        self.assertTrue(t.values(0))

    def test_sender_dedup_pause_mapping_disable_world_block_and_finish(self):
        item=m.eye_height_preset()
        owner=SimpleNamespace(lock=threading.RLock(),config={'oscHost':'127.0.0.1','oscPort':19000,'smoothGrowth':True,'profiles':{'manual':[item]}},motion_epoch=0,finish_generation=0,events=queue.Queue())
        stop=threading.Event();writes=[]
        with patch.object(m,'send_mapping',side_effect=lambda c,i,s:writes.append(s['value'])):
            worker=g.MotionSender(owner,stop)
            worker.closed.set();worker.thread.join() # Drive the same sender with a deterministic clock.
            with patch.object(g.time,'monotonic',return_value=0):worker.submit(('127.0.0.1',19000,'manual'),owner.config,[item],sources(1),None)
            with patch.object(g.time,'monotonic',return_value=1):worker.submit(worker.context,owner.config,[item],sources(4),None)
            worker.tick(5);self.assertGreater(writes[-1],1);self.assertLess(writes[-1],4)
            owner.finish_generation+=1;worker.tick(5);self.assertEqual(writes[-1],4)
            count=len(writes);worker.tick(6);worker.tick(7);self.assertEqual(count,len(writes))
            owner.config['profiles']['manual'][0]['enabled']=False;worker.tick(8);self.assertEqual(count,len(writes))
            owner.config['profiles']['manual'][0]['enabled']=True
            worker.discovery={'scalingAllowed':False};worker.sender.packets.clear();worker.tick(9);self.assertEqual(count,len(writes))
            worker.discovery=None;stop.set();worker.tick(10);self.assertEqual(count,len(writes))
            worker.close()

    def test_real_udp_transition_runs_while_polling_is_idle_and_stops(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1',0));receiver.settimeout(.3)
            item=m.eye_height_preset();owner=SimpleNamespace(lock=threading.RLock(),config={'oscHost':'127.0.0.1','oscPort':receiver.getsockname()[1],'smoothGrowth':True,'profiles':{'manual':[item]}},motion_epoch=0,finish_generation=0,events=queue.Queue())
            stop=threading.Event();worker=g.MotionSender(owner,stop)
            try:
                worker.submit(('127.0.0.1',owner.config['oscPort'],'manual'),owner.config,[item],sources(4),{'eyeHeight':1})
                with worker.lock:worker.transition.seconds=1
                first=receiver.recv(2048);second=receiver.recv(2048)
                self.assertNotEqual(first,second)
                owner.finish_generation+=1;time.sleep(.1)
                while True:
                    try:receiver.recv(2048)
                    except socket.timeout:break
                with self.assertRaises(socket.timeout):receiver.recv(2048)
            finally:worker.close()

    def test_submillimetre_ramp_suppressed_but_exact_endpoint_sent(self):
        item=m.eye_height_preset();owner=SimpleNamespace(lock=threading.RLock(),config={'oscHost':'127.0.0.1','oscPort':19000,'smoothGrowth':True,'profiles':{'manual':[item]}},motion_epoch=0,finish_generation=0,events=queue.Queue())
        stop=threading.Event();writes=[]
        with patch.object(m,'send_mapping',side_effect=lambda c,i,s:writes.append(s['value'])):
            worker=g.MotionSender(owner,stop);worker.closed.set();worker.thread.join()
            with patch.object(g.time,'monotonic',return_value=0):worker.submit(('127.0.0.1',19000,'manual'),owner.config,[item],sources(1),None)
            with patch.object(g.time,'monotonic',return_value=1):worker.submit(worker.context,owner.config,[item],sources(1.0004),None)
            worker.tick(2);self.assertEqual(writes,[1])
            worker.tick(200);self.assertEqual(writes,[1,1.0004])
            worker.close()
