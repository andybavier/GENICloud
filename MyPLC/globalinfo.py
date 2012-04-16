# Information on each GENICloud cluster.  Some of this info could be
# automatically obtained from the database.
sites = {
    'hplabs' :
    {
        'gc_eucacc' : '198.55.32.75',
        'myplc_sfaam' : '198.55.32.75',
        'node-srcrange' : '198.55.32.75-198.55.32.86',
        'vm-network' : '198.55.32.0/21',
        },
    'ucsd' :
    {
        'gc_eucacc' : '169.228.66.144',
        'myplc_sfaam' : '169.228.66.144',
        'node-srcrange' : '169.228.66.144-169.228.66.150',
        'vm-network' : '169.228.66.0/24'
        }
}

# The addresses from which admins are permitted to login to the nodes.
# Format: (address or network, name)
admins = [
    ('128.112.0.0/16', 'Princeton'),
    ('142.104.0.0/16', 'U Vic'),
    ('66.65.45.211', 'Marco Yuen'),
    ('24.108.136.153', 'Chris Pearson'),
    ('173.72.109.232', 'Andy Bavier')
]

# Allow access to the SFA only from GENICloud Central and testing machines
# This may not be necessary as long as sfatables is in place
sfa_access = ['128.112.139.111', '128.112.139.195']
