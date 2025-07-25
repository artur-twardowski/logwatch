import yaml
from utils import lw_assert
class Configuration:
    def __init__(self):
        self.subprocesses = []
        self.socket = None
        self.websocket = None
        self.late_join_buf_size = None
        self.stay_active = False

    def read(self, filename):
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
            lw_assert("server" in data, "Configuration file does not have \"server\" section")

            server_conf = data['server']
            
            self.socket = server_conf.get('socket-port', None)
            self.websocket = server_conf.get('websocket-port', None)
            self.late_join_buf_size = server_conf.get('late-joiners-buffer-size', None)
            self.stay_active = server_conf.get('stay-active', self.stay_active)

            for endpoint in data['server'].get('endpoints', []):
                lw_assert("type" in endpoint, "Endpoint type must be provided")
                lw_assert("name" in endpoint, "Endpoint name must be provided")

                if endpoint['type'] == 'subprocess':
                    lw_assert("command" in endpoint, "Subprocess endpoint must have a command specified")
                    self.subprocesses.append((endpoint['name'], endpoint['command']))

