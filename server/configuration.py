import yaml
from utils import lw_assert


class SubprocessConfig:
    def __init__(self, command):
        self.command = command


class SSHSessionConfig:
    def __init__(self, host, port, user, command, options):
        self.host = host
        self.port = port
        self.user = user
        self.command = command
        self.options = options


class ActionConfiguration:
    AWAIT_COMPLETION = 1

    def __init__(self, data, preconditions):
        self.data = data
        self.preconditions = preconditions

class Configuration:
    def __init__(self):
        self.endpoint_registers = {}
        self.actions = {}
        self.event_separation_rules = {}
        self.socket_addr = None
        self.socket_port = None
        self.websocket = None
        self.late_join_buf_size = None
        self.stay_active = False

    def _process_await_node(self, await_items):
        result = {}
        for item in await_items:
            if 'completed' in item:
                result[item['completed']] = ActionConfiguration.AWAIT_COMPLETION
        return result

    def _process_action_node(self, action_desc: dict, action_name: str):
        awaits = self._process_await_node(action_desc.get('await', []))

        if action_desc['type'] == 'subprocess':
            lw_assert("command" in action_desc, "Subprocess endpoint must have a command specified")
            command = action_desc['command'].strip().replace('\n', ';')

            self.actions[action_name] = ActionConfiguration(SubprocessConfig(command), awaits)
        elif action_desc['type'] == 'ssh':
            lw_assert("address" in action_desc, "SSH endpoint must have the host address specified")
            lw_assert("user" in action_desc, "SSH endpoint must have the user name specified")
            lw_assert("command" in action_desc, "SSH endpoint must have the command specified")

            command = action_desc['command'].strip().replace('\n', ';')

            self.actions[action_name] = ActionConfiguration(SSHSessionConfig(
                host=action_desc['address'],
                port=action_desc.get('port', None),
                user=action_desc['user'],
                command=command,
                options=action_desc.get('options', {})), awaits)

    def read(self, filename):
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
            lw_assert("server" in data, "Configuration file does not have \"server\" section")

            server_conf = data['server']
            
            self.socket_addr = server_conf.get('socket-addr', None)
            self.socket_port = server_conf.get('socket-port', None)
            self.websocket = server_conf.get('websocket-port', None)
            self.late_join_buf_size = server_conf.get('late-joiners-buffer-size', None)
            self.stay_active = server_conf.get('stay-active', self.stay_active)

            for endpoint in data['server'].get('endpoints', []):
                lw_assert("type" in endpoint, "Endpoint type must be provided")
                lw_assert("register" in endpoint, "Endpoint register must be provided")
                register = endpoint['register']
                name = endpoint.get("name", "&%c" % register)

                self._process_action_node(endpoint, name)
                self.endpoint_registers[register] = name

                self.event_separation_rules[name] = endpoint.get('event-separation', {'method': 'by-newline'})
            for action in data['server'].get('actions', []):
                lw_assert("type" in action, "Action type must be provided")
                lw_assert("name" in action, "Action name must be provided")

                self._process_action_node(action, action['name'])
                self.event_separation_rules[name] = action.get('event-separation', {'method': 'by-newline'})


