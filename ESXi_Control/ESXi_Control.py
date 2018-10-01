#
#  Provides a way to control various functions of an ESXi host through SSH.
#  If you have a paid license this probably isn't terribly useful as you could
#  use something like pyvmomi instead.
#
#  Ensure that SSH is enabled on your host.  Remember, unless you have
#  configured it otherwise, SSH is disabled when a host reboots.
#

import paramiko

class ESXiError(Exception):

    def __init__(self, code, message):
        self.code = code
        self.message = message


class ESXiHost(object):

    """
        Defines interfaces for connecting to, querying from and 
        controlling an ESXi host.
    """

    def __init__(self, host_name, username, password):

        """
          Initializes the ESXiHost object.

          params:

            host_name (string) - The ESXi host to connect to. 
            username (string)  - The username to use when connecting to the host.
            password (string)  - The password to use when connecting to the host.
        """

        self.network_name = host_name
        self.username = username
        self.password = password

        self.ssh_session = paramiko.SSHClient()
        self.ssh_session.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):

        """
          Connects to the given ESXi host using SSH.
        """

        self.ssh_session.connect(
            self.network_name,
            username=self.username,
            password=self.password
        )

    def connected(self):

        """
          Checks to see if the ssh connection to the ESXi host is still open.

          return:
            (bool) - True if the connection is still alive, False if not.
        """

        transp = self.ssh_session.get_transport()

        if transp is not None and transp.is_alive():

            return True

        else:

            return False

    def disconnect(self):

        """
          Disconnects from the ESXi host.
        """

        self.ssh_session.close()

    def get_maintenance_mode(self):

        """
          Gets the maintenance mode state of the ESXi host.
        """

        if self.connected():

            # Execute the command to get the maintenance mode state.
            stdin, stdout, stderr = self.ssh_session.exec_command(
                "esxcli system maintenanceMode get"
            )

            # Check the exit code of the command.  0 = success, 1 = failure
            if stdout.channel.recv_exit_status() == 0:
                result = stdout.readlines()

                # On success the command returns "Enabled" or "Disabled".
                for line in result:

                    if "Enabled" in line or "Disabled" in line:
                        state = line.split(" ")[0]
                        return state.strip()

            else:

                raise ESXiError(1000, "Unable to get maintenance mode state.")

        else:

            raise ESXiError(1000, "SSH not connected to host.")

    def enter_maintenance_mode(self):

        """
          Enables maintenance mode on the ESXi host.
        """

        if self.connected():

            # Get the existing maintenance mode state on the host.
            maintenance_mode_state = self.get_maintenance_mode()

            # If maintenance mode is already enabled, do nothing.
            if maintenance_mode_state == "Enabled":
                return

            # Execute the command to enter maintenance mode.
            stdin, stdout, stderr = self.ssh_session.exec_command(
                "vim-cmd hostsvc/maintenance_mode_enter"
            )

            # Check the exit code of the command.  0 = success, 1 = failure
            if not stdout.channel.recv_exit_status() == 0:
                raise ESXiError(1000, "Unable to enable maintenance mode on host.")

        else:

            raise ESXiError(1000, "SSH not connected to host.")

    def exit_maintenance_mode(self):

        """
          Disables maintenance mode on the ESXi host.
        """

        if self.connected():

            # Get the existing maintenance mode state on the host.
            maintenance_mode_state = self.get_maintenance_mode()

            # If maintenance mode is already disabled, do nothing.
            if maintenance_mode_state == "Disabled":
                return

            # Execute the command to exit maintenance mode.
            stdin, stdout, stderr = self.ssh_session.exec_command(
                "vim-cmd hostsvc/maintenance_mode_exit"
            )

            # Check the exit code of the command.  0 = success, 1 = failure
            if not stdout.channel.recv_exit_status() == 0:
                raise ESXiError(1000, "Unable to disable maintenance mode on host.")

        else:

            raise ESXiError(1000, "SSH not connected to host.")

    def shutdown(self, command):

        """
          Shuts down the ESXi host.

          command: (string) - shutdown command to execute.
            poweroff - Power off the system.
            reboot   - Reboot the system.

        """

        if self.connected():

            # Validate the specified command.
            if not isinstance(command, str) or command.lower() not in ['poweroff', 'reboot']:
                raise ESXiError(1000, "Command must be of type string and must be either 'poweroff' or 'reboot'.")

            # Get the existing maintenance mode state on the host.
            maintenance_mode_state = self.get_maintenance_mode()

            # If maintenance mode is disabled, raise an error.
            if maintenance_mode_state == "Disabled":
                raise ESXiError(1000, "ESXi host not in maintenance mode.")

            # Execute the command to shutdown the host.
            stdin, stdout, stderr = self.ssh_session.exec_command(
                "esxcli system shutdown {0}".format(command)
            )

            # Check the exit code of the command.  0 = success, 1 = failure
            if not stdout.channel.recv_exit_status() == 0:
                raise ESXiError(1000, "Unable to disable maintenance mode on host.")

        else:

            raise ESXiError(1000, "SSH not connected to host.")

    def get_all_vms(self):

        """
          Gets a list of all vms on the host.

          returns:

            vm_list (list) : A list of ESXiVM objects.
        """

        if self.connected():

            vms = []

            # Execute the command to get the list of vms.  Let awk parse the semi-complex output.
            stdin, stdout, stderr = self.ssh_session.exec_command(
                "vim-cmd vmsvc/getallvms | awk '$3 ~ /^\[/ {print $1\":\"$2\":\"$3\":\"$4\":\"$5\":\"$6}'"
            )

            # Check the exit code of the command.  0 = success, 1 = failure
            if not stdout.channel.recv_exit_status() == 0:
                raise ESXiError(1000, "Unable to get list of vms from host.")

            vm_list = stdout.readlines()

            if len(vm_list) > 0:

                # Put the vm info into a list.
                for vm in vm_list:

                    vm_data = vm.split(":")

                    # Skip saving the table header.
                    if vm_data[0].lower() != "vmid":
                        vms.append(
                            ESXiVm(self, vm_data)
                        )

                return vms

            else:

                return None

        else:

            raise ESXiError(1000, "SSH not connected to host.")

    def get_running_vms(self):

        """
          Gets a list of all running vms on the host.

          note:  The command "esxcli --formatter=csv vm process list" can be used to list
                 all of the running vms, but there doesn't appear to be a way to correlate
                 the vm info returned into an id to be used to control the vm.  VM names
                 aren't guaranteed to be unique.

          returns:

            vm_list: (list) A list of ESXiVm objects.
        """

        if self.connected():

            vms = []

            # Get a list of all vms.
            all_vms = self.get_all_vms()

            if all_vms is not None:

                # Go through the list and find the running vms.
                for vm in all_vms:

                    # If the vm is running, save it in the list.
                    if vm.get_powerstate == 'on':
                        vms.append(
                            vm
                        )

                return vms

            else:

                return None

        else:

            raise ESXiError(1000, "SSH not connected to host.")

    def find_vm_by_name(self, vm_name):

        """
          Finds a vm by name on the host.

          params:
            vm_name: (string) The name of the vm to find.

          returns:
            vm: (ESXiVm) The ESXiVm object that contains the vm details.
        """

        if self.connected():

            # Get a list of all vms.
            vms = self.get_all_vms()

            # Go through the list until the vm is found.
            for vm in vms:

                # If the vm is found, return it.
                if vm.name.lower() == vm_name.lower():

                    return vm

            return None

        else:

            raise ESXiError(1000, "SSH not connected to host.")

    def find_vm_by_id(self, vm_id):

        """
          Finds a vm by id on the host.

          params:
            vm_id: (integer) The id of the vm to find.

          returns:
            vm: (ESXiVm) The ESXiVm object that contains the vm details.
        """

        if self.connected():

            # Get a list of all vms.
            vms = self.get_all_vms()

            # Go through the list until the vm is found.
            for vm in vms:

                # If the vm is found, return it.
                if vm.id == vm_id:

                    return vm

            return None

        else:

            raise ESXiError(1000, "SSH not connected to host.")


class ESXiVm:

    def __init__(self, host, vm_data):

        self.id = int(vm_data[0])
        self.name = vm_data[1]
        self.datastore = vm_data[2]
        self.file = vm_data[3]
        self.guest_os = vm_data[4]
        self.version = vm_data[5]
        #self.comments = vm_data[6]

        self.host = host
        self.ssh_session = host.ssh_session

    @property
    def get_powerstate(self):

        """
          Gets the power state of the vm.

          returns:
            powerstate: (string) The power state of the vm. 'off' or 'on'
        """

        if self.host.connected():

            # Execute the command to get the power state.
            stdin, stdout, stderr = self.ssh_session.exec_command(
                "vim-cmd vmsvc/power.getstate {0}".format(self.id)
            )

            # Check the exit code of the command.  0 = success, 1 = failure
            if not stdout.channel.recv_exit_status() == 0:

                raise ESXiError(1000, "Unable to query the power state of the specified vm.")

            result = stdout.readlines()

            # Got through the lines, the state will be prefaced by the word 'Powered'.
            for line in result:

                if "Powered " in line:

                    state = line.split(" ")[1]

                    return state.strip()

            return None

        else:

            raise ESXiError(1000, "SSH not connected to host.")

    def set_powerstate(self, state):

        """
          Sets the power state of the vm.

          params:
            powerstate: (string) The power state of the vm. 'off' or 'on'
        """

        if self.host.connected():

            # Validate the specified state.
            if not isinstance(state, str) or state.lower() not in ['on', 'off']:

                raise ESXiError(1000, "Command must be of type string and must be either 'on' or 'off'.")

            # Verify that the vm isn't already in the specified state.
            if self.get_powerstate == state:

                return

            # Execute the command to set the power state.
            stdin, stdout, stderr = self.ssh_session.exec_command(
                "vim-cmd vmsvc/power.{0} {1}".format(state, self.id)
            )

            # Check the exit code of the command.  0 = success, 1 = failure
            if not stdout.channel.recv_exit_status() == 0:
                raise ESXiError(1000, "Unable to set the power state of the specified vm.")

            # Just read the lines for completeness.
            stdout.readlines()

        else:

            raise ESXiError(1000, "SSH not connected to host.")

    def shutdown(self):

        """
          Shuts down the vm.

          params:
            vm: (ESXiVm) The ESXiVm object that contains the vm details.
         """

        if self.host.connected():

            # Verify that the vm isn't already shutdown.
            if self.get_powerstate == 'off':
                return

            # Execute the command to set the power state.
            stdin, stdout, stderr = self.ssh_session.exec_command(
                "vim-cmd vmsvc/power.shutdown {0}".format(self.id)
            )

            # Check the exit code of the command.  0 = success, 1 = failure
            if not stdout.channel.recv_exit_status() == 0:
                raise ESXiError(1000, "Unable to shutdown the specified vm.")

            # Just read the lines for completeness.
            stdout.readlines()

        else:

            raise ESXiError(1000, "SSH not connected to host.")
