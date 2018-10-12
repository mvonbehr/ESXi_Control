#
#  Provides a way to control various functions of an ESXi host through SSH.
#  If you have a paid license this probably isn't terribly useful as you could
#  use something like pyvmomi instead.
#
#  Ensure that SSH is enabled on your host.  Remember, unless you have
#  configured it otherwise, SSH is disabled when a host reboots.
#

import re
import paramiko
from enum import Enum, EnumMeta


class ESXIErrors(object):

    """
        Defines constants for api errors.
    """

    class SSHNotConnected(Enum):
        code = -1000
        message = "SSH not connected to host."

    class Host_MaintenanceModeEnter_Failed(Enum):
        code = -1010
        message = "Unable to enable maintenance mode on host."

    class Host_MaintenanceModeExit_Failed(Enum):
        code = -1011
        message = "Unable to disable maintenance mode on host."

    class Host_MaintenanceModeQuery_Failed(Enum):
        code = -1012
        message = "Unable to get maintenance mode state."

    class Host_Shutdown_InvalidCommand(Enum):
        code = -1020
        message = "Command must be of type string and must be either 'poweroff' or 'reboot'."

    class Host_Shutdown_Failed(Enum):
        code = -1021
        message = "Unable to shutdown host."

    class Host_VMQuery_Failed(Enum):
        code = -1030
        message = "Unable to get list of vms from host."

    class VM_PowerStateQuery_Failed(Enum):
        code = -1040
        message = "Unable to query the power state of the specified vm."

    class VM_Hibernate_Failed(Enum):
        code = -1050
        message = "Unable to hibernate the specified vm."

    class VM_PowerOn_Failed(Enum):
        code = -1060
        message = "Unable to power on the specified vm."

    class VM_PowerOff_Failed(Enum):
        code = -1070
        message = "Unable to power off the specified vm."

    class VM_Reboot_Failed(Enum):
        code = -1080
        message = "Unable to reboot the specified vm."

    class VM_Reset_Failed(Enum):
        code = -1090
        message = "Unable to reset the specified vm."

    class VM_Shutdown_Failed(Enum):
        code = -1100
        message = "Unable to shutdown the specified vm."

    class VM_Suspend_Failed(Enum):
        code = -1110
        message = "Unable to suspend the specified vm."


class ESXiError(Exception):

    """
        ESXi exception class that handles taking error constants or classic
        code/message errors.
    """

    def __init__(self, *args, **kwargs):

        # See if an error enum was passed in.
        if len(args) > 0 and isinstance(args[0], EnumMeta):

            # Save the code and message into the exception.
            self.code = args[0]['code'].value
            self.message = args[0]['message'].value

            # See if there are more unnamed args.  If so, use the next
            # one for the reason.
            if len(args) > 1 and args[1] is not None:

                self.reason = args[1]

            # See if reason was specified in the named args.
            elif "reason" in kwargs:

                self.reason = kwargs['reason']

            else:

                self.reason = None

        # Error enum not passed in, use the params as the exception values.
        else:

            # Get the code passed in.
            if len(args) > 0:

                self.code = args[0]

            elif "code" in kwargs:

                self.code = kwargs['code']

            # Get the message passed in.
            if len(args) > 1:

                self.message = args[1]

            elif "message" in kwargs:

                self.message = kwargs['message']

            # Get the reason passed in.
            if len(args) > 2:

                self.reason = args[2]

            elif "reason" in kwargs:

                self.reason = kwargs['reason']

            else:

                self.reason = None


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

                raise ESXiError(ESXIErrors.Host_MaintenanceModeQuery_Failed)

        else:

            raise ESXiError(ESXIErrors.SSHNotConnected)

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

                raise ESXiError(ESXIErrors.Host_MaintenanceModeEnter_Failed)

        else:

            raise ESXiError(ESXIErrors.SSHNotConnected)

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
                raise ESXiError(ESXIErrors.Host_MaintenanceModeExit_Failed)

        else:

            raise ESXiError(ESXIErrors.SSHNotConnected)

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

                raise ESXiError(ESXIErrors.Host_Shutdown_InvalidCommand)

            # Get the existing maintenance mode state on the host.
            # maintenance_mode_state = self.get_maintenance_mode()

            # If maintenance mode is disabled, raise an error.
            # if maintenance_mode_state == "Disabled":

            #    raise ESXiError(1000, "ESXi host not in maintenance mode.")

            # Execute the command to shutdown the host.
            stdin, stdout, stderr = self.ssh_session.exec_command(
                "esxcli system shutdown {0}".format(command)
            )

            # Check the exit code of the command.  0 = success, 1 = failure
            if not stdout.channel.recv_exit_status() == 0:

                raise ESXiError(ESXIErrors.Host_Shutdown_Failed)

        else:

            raise ESXiError(ESXIErrors.SSHNotConnected)

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
                raise ESXiError(ESXIErrors.Host_VMQuery_Failed)

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

            raise ESXiError(ESXIErrors.SSHNotConnected)

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
                    if vm.power_getstate() == 'on':
                        vms.append(
                            vm
                        )

                return vms

            else:

                return None

        else:

            raise ESXiError(ESXIErrors.SSHNotConnected)

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

            raise ESXiError(ESXIErrors.SSHNotConnected)

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

            raise ESXiError(ESXIErrors.SSHNotConnected)


class ESXiVm:

    def __init__(self, host, vm_data):

        self.id = int(vm_data[0])
        self.name = vm_data[1]
        self.datastore = vm_data[2]
        self.file = vm_data[3]
        self.guest_os = vm_data[4]
        self.version = vm_data[5]

        self.host = host
        self.ssh_session = host.ssh_session

    def ssh_check(*args, **kwargs):
        """
          Used to create a decorator that performs a check to see if SSH is
          still connected to a host.

          returns:
            ssh_check_wrapper: (function) The wrapper function that
            performs the SSH check.
        """

        # Get the function we are trying to wrap.
        wrapped_function = args[0]

        def ssh_check_wrapper(*args_list, **kwargs_list):
            """
              Performs a check to see if SSH is still connected to a host.

              returns:
                The return value of the wrapped function.
            """

            # Check if SSH is still connected.
            if not args[0].host.connected():

                raise ESXiError(ESXIErrors.SSHNotConnected)

            # Call the wrapped function.
            return wrapped_function(*args_list, **kwargs_list)

        return ssh_check_wrapper

    @ssh_check
    def power_getstate(self):

        """
          Gets the power state of the vm.

          returns:
            powerstate: (string) The power state of the vm. 'off' or 'on' or 'suspended'
        """

        # Execute the command to get the power state.
        stdin, stdout, stderr = self.ssh_session.exec_command(
            "vim-cmd vmsvc/power.getstate {0}".format(self.id)
        )

        # Check the exit code of the command.  0 = success, 1 = failure
        if not stdout.channel.recv_exit_status() == 0:

            raise ESXiError(ESXIErrors.VM_PowerStateQuery_Failed)

        result = stdout.readlines()

        # Got through the lines, the state will be prefaced by the word 'Powered'.
        for line in result:

            if "Powered " in line:

                state = line.split(" ")[1]

                return state.strip()

            elif "Suspended" in line:

                return "suspended"

        return None

    @ssh_check
    def power_hibernate(self):

        """
          Hibernates the VM.
        """

        # Verify that the vm isn't already in the specified state.
        if self.power_getstate() == 'suspended':

            return

        # Execute the command to set the power state.
        stdin, stdout, stderr = self.ssh_session.exec_command(
            "vim-cmd vmsvc/power.hibernate {0}".format(self.id)
        )

        # Read lines just for completeness.
        stdout.readlines()

        # Check the exit code of the command.  0 = success, 1 = failure
        if not stdout.channel.recv_exit_status() == 0:

            # Do a quick check to see if the vim.fault was returned in stderr.
            vim_status = stderr.readlines()

            if "vim.fault" in vim_status[0]:

                # Get the actual vim fault.
                vim_fault = re.search("(?:vim\.fault)[.]([a-zA-Z]*)", vim_status[0])
                vim_fault = vim_fault.group(1)

                raise ESXiError(
                    1000,
                    "Unable to hibernate the specified vm.",
                    "({0}) The attempted operation cannot be performed "
                    "in the current state. ({1})".format(vim_fault, self.power_getstate().capitalize())
                )

            else:

                raise ESXiError(ESXIErrors.VM_Hibernate_Failed)

    @ssh_check
    def power_on(self):

        """
          Powers on the VM.
        """

        # Verify that the vm isn't already in the specified state.
        if self.power_getstate() == 'on':

            return

        # Execute the command to set the power state.
        stdin, stdout, stderr = self.ssh_session.exec_command(
            "vim-cmd vmsvc/power.on {0}".format(self.id)
        )

        # Read lines just for completeness.
        stdout.readlines()

        # Check the exit code of the command.  0 = success, 1 = failure
        if not stdout.channel.recv_exit_status() == 0:

            # Do a quick check to see if the vim.fault was returned in stderr.
            vim_status = stderr.readlines()

            if "vim.fault" in vim_status[0]:

                # Get the actual vim fault.
                vim_fault = re.search("(?:vim\.fault)[.]([a-zA-Z]*)", vim_status[0])
                vim_fault = vim_fault.group(1)

                raise ESXiError(
                    ESXIErrors.VM_PowerOn_Failed,
                    "({0}) The attempted operation cannot be performed "
                    "in the current state. ({1})".format(
                        vim_fault,
                        self.power_getstate().capitalize()
                    )
                )

            else:

                raise ESXiError(ESXIErrors.VM_PowerOn_Failed)

    @ssh_check
    def power_off(self):

        """
          Powers off the VM.
        """

        # Verify that the vm isn't already in the specified state.
        if self.power_getstate() == 'off':

            return

        # Execute the command to set the power state.
        stdin, stdout, stderr = self.ssh_session.exec_command(
            "vim-cmd vmsvc/power.off {0}".format(self.id)
        )

        # Read lines just for completeness.
        stdout.readlines()

        # Check the exit code of the command.  0 = success, 1 = failure
        if not stdout.channel.recv_exit_status() == 0:

            # Do a quick check to see if the vim.fault was returned in stderr.
            vim_status = stderr.readlines()

            if "vim.fault" in vim_status[0]:

                # Get the actual vim fault.
                vim_fault = re.search("(?:vim\.fault)[.]([a-zA-Z]*)", vim_status[0])
                vim_fault = vim_fault.group(1)

                raise ESXiError(
                    ESXIErrors.VM_PowerOff_Failed,
                    "({0}) The attempted operation cannot be performed "
                    "in the current state. ({1})".format(
                        vim_fault,
                        self.power_getstate().capitalize()
                    )
                )

            else:

                raise ESXiError(ESXIErrors.VM_PowerOff_Failed)

    @ssh_check
    def power_reboot(self):

        """
          Reboots the VM.
        """

        # Execute the command to set the power state.
        stdin, stdout, stderr = self.ssh_session.exec_command(
            "vim-cmd vmsvc/power.reboot {0}".format(self.id)
        )

        # Read lines just for completeness.
        stdout.readlines()

        # Check the exit code of the command.  0 = success, 1 = failure
        if not stdout.channel.recv_exit_status() == 0:

            # Do a quick check to see if the vim.fault was returned in stderr.
            vim_status = stderr.readlines()

            if "vim.fault" in vim_status[0]:

                # Get the actual vim fault.
                vim_fault = re.search("(?:vim\.fault)[.]([a-zA-Z]*)", vim_status[0])
                vim_fault = vim_fault.group(1)

                raise ESXiError(
                    ESXIErrors.VM_Reboot_Failed,
                    "({0}) The attempted operation cannot be performed "
                    "in the current state. ({1})".format(
                        vim_fault,
                        self.power_getstate().capitalize()
                    )
                )

            else:

                raise ESXiError(ESXIErrors.VM_Reboot_Failed)

    @ssh_check
    def power_reset(self):

        """
          Resets the VM.
        """

        # Execute the command to set the power state.
        stdin, stdout, stderr = self.ssh_session.exec_command(
            "vim-cmd vmsvc/power.reset {0}".format(self.id)
        )

        # Read lines just for completeness.
        stdout.readlines()

        # Check the exit code of the command.  0 = success, 1 = failure
        if not stdout.channel.recv_exit_status() == 0:

            # Do a quick check to see if the vim.fault was returned in stderr.
            vim_status = stderr.readlines()

            if "vim.fault" in vim_status[0]:

                # Get the actual vim fault.
                vim_fault = re.search("(?:vim\.fault)[.]([a-zA-Z]*)", vim_status[0])
                vim_fault = vim_fault.group(1)

                raise ESXiError(
                    ESXIErrors.VM_Reset_Failed,
                    "({0}) The attempted operation cannot be performed "
                    "in the current state. ({1})".format(
                        vim_fault,
                        self.power_getstate().capitalize()
                    )
                )

            else:

                raise ESXiError(ESXIErrors.VM_Reset_Failed)

    @ssh_check
    def power_shutdown(self):

        """
          Shuts down the VM.
        """

        # Verify that the vm isn't already in the specified state.
        if self.power_getstate() == 'off':

            return

        # Execute the command to set the power state.
        stdin, stdout, stderr = self.ssh_session.exec_command(
            "vim-cmd vmsvc/power.shutdown {0}".format(self.id)
        )

        # Read lines just for completeness.
        stdout.readlines()

        # Check the exit code of the command.  0 = success, 1 = failure
        if not stdout.channel.recv_exit_status() == 0:

            # Do a quick check to see if the vim.fault was returned in stderr.
            vim_status = stderr.readlines()

            if "vim.fault" in vim_status[0]:

                # Get the actual vim fault.
                vim_fault = re.search("(?:vim\.fault)[.]([a-zA-Z]*)", vim_status[0])
                vim_fault = vim_fault.group(1)

                raise ESXiError(
                    ESXIErrors.VM_Shutdown_Failed,
                    "({0}) The attempted operation cannot be performed "
                    "in the current state. ({1})".format(
                        vim_fault,
                        self.power_getstate().capitalize()
                    )
                )

            else:

                raise ESXiError(ESXIErrors.VM_Shutdown_Failed)

    @ssh_check
    def power_suspend(self):

        """
          Suspends the VM.
        """

        # Verify that the vm isn't already in the specified state.
        if self.power_getstate() == 'suspended':

            return

        # Execute the command to set the power state.
        stdin, stdout, stderr = self.ssh_session.exec_command(
            "vim-cmd vmsvc/power.suspend {0}".format(self.id)
        )

        # Read lines just for completeness.
        stdout.readlines()

        # Check the exit code of the command.  0 = success, 1 = failure
        if not stdout.channel.recv_exit_status() == 0:

            # Do a quick check to see if the vim.fault was returned in stderr.
            vim_status = stderr.readlines()

            if "vim.fault" in vim_status[0]:

                # Get the actual vim fault.
                vim_fault = re.search("(?:vim\.fault)[.]([a-zA-Z]*)", vim_status[0])
                vim_fault = vim_fault.group(1)

                raise ESXiError(
                    ESXIErrors.VM_Suspend_Failed,
                    "({0}) The attempted operation cannot be performed "
                    "in the current state. ({1})".format(vim_fault, self.power_getstate().capitalize())
                )

            else:

                raise ESXiError(ESXIErrors.VM_Suspend_Failed)

    @ssh_check
    def power_suspendresume(self):
        pass
