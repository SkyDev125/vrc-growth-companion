import copy,json,socket,struct,threading,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch,MagicMock
import avatar_mapping as mapping
import chilloutvr


def query_tree():
    return {'CONTENTS':{'avatar':{'CONTENTS':{
        'change':{'TYPE':'s','VALUE':['98c9e3bc-d0da-4f24-8de3-111111111111']},
        'profile':{'CONTENTS':{'change':{'TYPE':'s','VALUE':['Default']}}},
        'parameters':{'CONTENTS':{
            'ScaleSlider':{'TYPE':'f','ACCESS':3},
            'Count':{'TYPE':'i','ACCESS':3},
            'Enabled':{'TYPE':'T','ACCESS':3},
            'Velocity':{'TYPE':'f','ACCESS':1}}}}}}}


class ChilloutVRTests(unittest.TestCase):
    def test_real_oscquery_discovery_advertised_port_and_udp_change_only(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
            receiver.bind(('127.0.0.1',0));receiver.settimeout(.1)
            info={'NAME':'ChilloutVR-ABCDEF','OSC_PORT':receiver.getsockname()[1]}
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    data=json.dumps(info if self.path=='/?HOST_INFO' else query_tree()).encode()
                    self.send_response(200);self.end_headers();self.wfile.write(data)
                def log_message(self,*args):pass
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            config={'targetApp':'chilloutvr','oscHost':'127.0.0.1','oscPort':9000,'oscQueryPort':server.server_port}
            try:
                discovery=mapping.discover(config,browse=False)
                self.assertEqual(discovery['oscPort'],receiver.getsockname()[1])
                self.assertEqual(discovery['avatarProfile'],'Default')
                self.assertTrue(mapping.profile_key(discovery,'chilloutvr').startswith('chilloutvr:98c9'))
                item={**chilloutvr.scale_mapping(),'target':'/avatar/parameters/ScaleSlider'}
                source={'value':5,'originalValue':2,'unit':'m'}
                self.assertTrue(mapping.can_send(item,{'height':source},discovery))
                sender=mapping.ChangedSender();config['oscPort']=discovery['oscPort']
                self.assertTrue(sender.send(config,item,source))
                packet=receiver.recv(1024)
                self.assertIn(b'/avatar/parameters/ScaleSlider\0',packet)
                self.assertEqual(struct.unpack('>f',packet[-4:])[0],.5)
                self.assertFalse(sender.send(config,item,source))
                with self.assertRaises(socket.timeout):receiver.recv(1024)
                info['NAME']='VRChat-ABCDEF'
                self.assertIsNone(mapping.discover(config,browse=False))
            finally:server.shutdown();server.server_close();worker.join()

    def test_writable_types_and_avatar_profile_isolation(self):
        tree=query_tree();discovery=mapping.parse_tree(tree,'chilloutvr')
        self.assertEqual(discovery['parameters'],{'/avatar/parameters/ScaleSlider':'float','/avatar/parameters/Count':'int','/avatar/parameters/Enabled':'bool'})
        self.assertFalse(discovery['allParameters']['/avatar/parameters/Velocity']['writable'])
        self.assertIsNone(discovery['eyeHeight'])
        item={**chilloutvr.scale_mapping(),'target':'/avatar/parameters/ScaleSlider'}
        for wrong in (None,{'platform':'vrchat'}, {**discovery,'parameters':{}}, {**discovery,'parameters':{item['target']:'int'}}):
            self.assertFalse(mapping.can_send(item,{'height':{}},wrong))
        self.assertNotEqual(mapping.profile_key(discovery),mapping.profile_key(discovery,'chilloutvr'))
        self.assertNotEqual(mapping.profile_key(discovery,'chilloutvr'),mapping.profile_key({**discovery,'avatarProfile':'Large'},'chilloutvr'))
        config={'profiles':{chilloutvr.MANUAL_PROFILE:[],mapping.profile_key(discovery,'chilloutvr'):[]}}
        mapping.migrate_profiles(config)
        self.assertEqual(config['profiles'][chilloutvr.MANUAL_PROFILE],[])

    def test_no_universal_scale_endpoint_no_vrchat_limits_and_native_types(self):
        preset=chilloutvr.scale_mapping()
        self.assertEqual(preset['target'],'')
        for target in ('','/avatar/eyeheight','/avatar/change','/avatar/profile/change','/input/Jump','/chatbox/input'):
            with self.assertRaises(ValueError):mapping.validate_mapping({**preset,'target':target})
        item={**preset,'target':'Capacity','mode':'value','source':'volume'}
        self.assertEqual(mapping.mapped_value(item,{'value':25000,'unit':'L'}),25000)
        for enabled in (True,False):
            packet=mapping.encode_parameter('/avatar/parameters/Enabled','bool',enabled,'chilloutvr')
            self.assertTrue(packet.endswith(b',T\0\0' if enabled else b',F\0\0'))
        packet=mapping.encode_parameter('/avatar/parameters/Count','int',42,'chilloutvr')
        self.assertEqual(struct.unpack('>i',packet[-4:])[0],42)

    def test_mdns_only_uses_chilloutvr_services_on_selected_host(self):
        zc=MagicMock();info=MagicMock();info.parsed_addresses.return_value=['192.168.1.42'];info.port=12345
        zc.get_service_info.return_value=info
        def browse(instance,kind,listener):
            listener.add_service(instance,kind,'VRChat-test._oscjson._tcp.local.')
            listener.add_service(instance,kind,'ChilloutVR-test._oscjson._tcp.local.')
            return MagicMock()
        with patch.object(mapping,'Zeroconf',return_value=zc),patch.object(mapping,'ServiceBrowser',side_effect=browse),patch.object(mapping.time,'sleep'):
            self.assertEqual(mapping.mdns_ports('192.168.1.42',platform='chilloutvr'),[12345])
        self.assertEqual(zc.get_service_info.call_count,1)
        self.assertIn('ChilloutVR',zc.get_service_info.call_args.args[1])
