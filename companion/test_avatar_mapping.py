import copy
import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
import avatar_mapping as m
import vrchat_companion as core


class MappingTests(unittest.TestCase):
    def item(self, **changes):
        return dict(source='tail',target='/avatar/parameters/Tail',kind='float',mode='range',inputMin=0,inputMax=200,outputMin=0,outputMax=1,**changes)

    def test_eye_height_preset_and_legacy_migration(self):
        config={'syncHeight':False,'profiles':{'avtr_a':[]}}
        m.migrate_profiles(config)
        item=config['profiles']['avtr_a'][0]
        self.assertFalse(item['enabled'])
        self.assertEqual(item['target'],'/avatar/eyeheight')
        m.migrate_profiles(config)
        self.assertEqual(len(config['profiles']['avtr_a']),1)
        self.assertTrue(m.can_send(item,{'height':{}},None))
        self.assertEqual(m.mapped_value(m.eye_height_preset(),{'value':20000}),10000)
        self.assertEqual(m.mapped_value(m.eye_height_preset(),{'value':3}),3)
        self.assertEqual(m.encode_parameter('/avatar/eyeheight','float',3),core.encode_eyeheight_packet(3))

    def test_range_clamps_and_can_reverse(self):
        item=self.item()
        for value,expected in [(-1,0),(100,.5),(201,1)]:
            self.assertEqual(m.mapped_value(item,{'value':value}),expected)
        item.update(outputMin=1,outputMax=-1)
        self.assertEqual(m.mapped_value(item,{'value':150}),-.5)

    def test_ratio_uses_raw_original_unit_not_formatted_display(self):
        item=self.item(); item['mode']='ratio'
        self.assertEqual(m.mapped_value(item,{'value':11024.58,'originalValue':9187.15}),1.2)
        with self.assertRaises(ValueError): m.mapped_value(item,{'value':1,'originalValue':0})

    def test_boolean_threshold_and_wire_tags(self):
        item=self.item(); item.update(kind='bool',mode='threshold',threshold=10)
        for value,expected in [(9,False),(10,True)]:
            result=m.mapped_value(item,{'value':value})
            self.assertIs(result,expected)
            self.assertTrue(m.encode_parameter(item['target'],'bool',result).endswith(b',T\0\0' if expected else b',F\0\0'))

    def test_integer_rounding_and_overflow(self):
        item=self.item(); item.update(kind='int',mode='value')
        self.assertEqual(m.mapped_value(item,{'value':-1.5}),-2)
        self.assertEqual(m.mapped_value(item,{'value':1.5}),2)
        for value in (2**31,float('inf')):
            with self.assertRaises(ValueError): m.mapped_value(item,{'value':value})

    def test_rejects_unsafe_addresses_and_invalid_limits(self):
        for target in ('/chatbox/input','/input/MoveForward','/avatar/parameters/*',''):
            with self.assertRaises(ValueError): m.parameter_address(target)
        self.assertEqual(m.parameter_address('Tail'),'/avatar/parameters/Tail')
        for changes in ({'inputMax':0},{'outputMax':'nan'},{'kind':'bool'},{'mode':'threshold'},{'mode':'unknown'}):
            item=self.item();item.update(changes)
            with self.assertRaises(ValueError): m.validate_mapping(item)

    def tree(self):
        return {'CONTENTS':{'avatar':{'CONTENTS':{
            'change':{'TYPE':'s','VALUE':['avtr_test'],'ACCESS':1},
            'parameters':{'CONTENTS':{
                'Tail':{'TYPE':'f','ACCESS':3},'ReadOnly':{'TYPE':'f','ACCESS':1},
                'Mode':{'TYPE':'i','ACCESS':2},'Toggle':{'TYPE':'T','ACCESS':3},
                'Array':{'TYPE':'ff','ACCESS':3}}}}}}}

    def test_discovery_only_exposes_writable_scalar_parameters(self):
        found=m.parse_tree(self.tree())
        self.assertEqual(found['avatar'],'avtr_test')
        self.assertEqual(found['parameters'],{m.PREFIX+'Tail':'float',m.PREFIX+'Mode':'int',m.PREFIX+'Toggle':'bool'})
        sources={'tail':{'value':100}}
        self.assertTrue(m.can_send(self.item(),sources,found))
        item=self.item();item['target']=m.PREFIX+'ReadOnly'
        self.assertFalse(m.can_send(item,sources,found))
        item['target']=m.PREFIX+'Missing'
        self.assertFalse(m.can_send(item,sources,found))
        item['target']=m.PREFIX+'Mode'
        self.assertFalse(m.can_send(item,sources,found))
        self.assertTrue(m.can_send(item,sources,None))
        self.assertFalse(m.can_send(item,{},None))

    def test_avatar_profiles_do_not_reuse_previous_avatar(self):
        self.assertEqual(m.profile_key({'avatar':'avtr_a'}),'avtr_a')
        self.assertEqual(m.profile_key({'avatar':'avtr_b'}),'avtr_b')
        self.assertEqual(m.profile_key(None),'manual')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config.json'
            data={'serverUrl':core.DEFAULT_URL,'oscHost':'127.0.0.1','oscPort':9000,'profiles':{'avtr_a':[self.item()]},'syncHeight':False}
            core.save_config(data,path)
            loaded=core.load_config(path)
            self.assertEqual(loaded['profiles'],data['profiles'])
            self.assertFalse(loaded['syncHeight'])

    def test_http_discovery_and_measurements_to_real_udp(self):
        tree=self.tree()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                value=tree if self.path=='/' else {'measurements':[{'id':'tail','name':'Tail','value':100,'originalValue':50,'unit':'cm'}]}
                raw=json.dumps(value).encode()
                self.send_response(200);self.end_headers();self.wfile.write(raw)
            def log_message(self,*args): pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            config={'serverUrl':f'http://127.0.0.1:{server.server_port}','oscHost':'127.0.0.1','oscQueryPort':server.server_port}
            found=m.discover(config,browse=False)
            self.assertEqual(found['avatar'],'avtr_test')
            sources=m.fetch_measurements(config)
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
                receiver.bind(('127.0.0.1',0));receiver.settimeout(2)
                config['oscPort']=receiver.getsockname()[1]
                m.send_mapping(config,self.item(),sources[0])
                packet,_=receiver.recvfrom(4096)
                self.assertEqual(packet,m.encode_parameter('Tail','float',.5))
        finally:
            server.shutdown();server.server_close();thread.join(2)

    def test_discovery_failure_returns_none(self):
        with patch.object(m,'query_json',side_effect=OSError('offline')):
            self.assertIsNone(m.discover({'oscHost':'127.0.0.1'},browse=False))


if __name__=='__main__': unittest.main()


class ChangedSenderTests(unittest.TestCase):
    def test_same_wire_value_is_sent_once_and_changed_value_is_sent(self):
        sender=m.ChangedSender();sender.begin(('avatar-a',9000))
        item=m.eye_height_preset();config={'oscHost':'127.0.0.1','oscPort':9000}
        with patch.object(m,'send_mapping') as send:
            self.assertTrue(sender.send(config,item,{'value':3}))
            for value in [3,3,3+1e-10]:self.assertFalse(sender.send(config,item,{'value':value}))
            self.assertTrue(sender.send(config,item,{'value':4}))
            self.assertEqual(send.call_count,2)
            sender.begin(('avatar-b',9000))
            self.assertTrue(sender.send(config,item,{'value':4}))
            sender.prune(set())
            self.assertTrue(sender.send(config,item,{'value':4}))
    def test_failed_udp_write_is_retried(self):
        sender=m.ChangedSender();sender.begin('avatar-a')
        with patch.object(m,'send_mapping',side_effect=[OSError('unavailable'),None]) as send:
            with self.assertRaises(OSError):sender.send({'oscHost':'127.0.0.1','oscPort':9000},m.eye_height_preset(),{'value':3})
            self.assertTrue(sender.send({'oscHost':'127.0.0.1','oscPort':9000},m.eye_height_preset(),{'value':3}))
            self.assertEqual(send.call_count,2)
    def test_udp_receiver_gets_no_repeated_unchanged_datagrams(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1',0));receiver.settimeout(.1)
            config={'oscHost':'127.0.0.1','oscPort':receiver.getsockname()[1]}
            sender=m.ChangedSender();sender.begin('avatar-a')
            for value in [3,3,3,4,4]:sender.send(config,m.eye_height_preset(),{'value':value})
            self.assertEqual(receiver.recvfrom(4096)[0],core.encode_eyeheight_packet(3))
            self.assertEqual(receiver.recvfrom(4096)[0],core.encode_eyeheight_packet(4))
            with self.assertRaises(socket.timeout):receiver.recvfrom(4096)
