# pip install boto
# pip install fabric

from fabric.api import *
import aws, time

@task
def provision_activemq():
    node = aws.provision_with_boto('broker')
    with connection_to_node(node):
        setup_puppet_standalone()
        apply_manifest("broker-activemq", node.hostname)

@task
def provision_node(node_name):
    stomp_host = aws.public_dns('broker')
    node = aws.provision_with_boto(node_name)
    with connection_to_node(node):
        setup_puppet_standalone()
        apply_manifest("mcollective-node", stomp_host)

@task
def mco_ping():
    node = aws.provision_with_boto('broker')
    with connection_to_node(node):
        run('mco ping')

@task
def shell(node_name):
    node = aws.provision_with_boto(node_name)
    wait_for_ssh_connection(node)
    command = "ssh -i %s -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no %s@%s"
    print command % (node.ssh_key_file, node.ssh_user, node.hostname)

@task
def cleanup(node_name = None):
    config = aws.read_config()
    if node_name:
        if config.has_section(node_name):
            aws.terminate_instance(node_name)
    else:
        for section in config.sections():
            aws.terminate_instance(section)

@task
def destroy():
    aws.terminate_all_instances()

# --------------------------------------------------------------------
# Common provisioning functions
# --------------------------------------------------------------------

def connection_to_node(node):
    wait_for_ssh_connection(node)
    return settings(host_string=node.hostname, user=node.ssh_user, key_filename=node.ssh_key_file)

def wait_for_ssh_connection(node):
    with settings(warn_only=True):
        result = check_ssh(node)
        while result.failed:
            print 'Waiting for SSH service ...'
            time.sleep(10)
            result = check_ssh(node)

def check_ssh(node):
    return local('nc -z -v -w 10 %s 22' % node.hostname)

def setup_puppet_standalone():
    with settings(warn_only=True):
        result = run('puppet --version')
    if result.failed:
        sudo('yum install -y puppet')
    with settings(warn_only=True):
        run("rm -f ec2-setup.tgz")
        run("rm -rf puppet/")
    local("tar czf /tmp/ec2-setup.tgz puppet/*")
    put("/tmp/ec2-setup.tgz", ".")
    run("tar xzf ec2-setup.tgz")

def apply_manifest(manifest, stomp_host):
    puppet_root = "/home/ec2-user/puppet"
    command = "FACTER_stomp_host=%s puppet apply --modulepath=%s/modules %s/manifests/%s.pp"
    sudo(command % (stomp_host, puppet_root, puppet_root, manifest))
