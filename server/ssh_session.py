from .subprocess import SubprocessCommunication
from .configuration import SSHSessionConfig

class SSHSessionCommunication(SubprocessCommunication):
    def __init__(self, config: SSHSessionConfig, endpoint_name, server_manager):
        cmd = "ssh %s@%s" % (config.user, config.host)
        if config.port is not None:
            cmd += " -p %d" % config.port
        for key, value in config.options.items():
            cmd += " -o %s=%s" % (key, value)
        cmd += " '%s'" % config.command
        super().__init__(cmd, endpoint_name, server_manager)
