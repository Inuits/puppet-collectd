# Class: collectd
#
# This module manages collectd
#
# Parameters:
#
# Actions:
#
# Requires:
#
# Sample Usage:
#
# [Remember: No empty lines between comments and class definition]
class collectd (
  $pkgname              = $::collectd::params::pkgname,
  $pkgversion           = 'latest',
  $config_file          = $::collectd::params::config_file,
  $config_template_name = $::collectd::params::config_template_name,
  $config_dir           = $::collectd::params::config_dir,
  $purge                = $::collectd::params::purge,
  $service_name         = $::collectd::params::service_name,
  $service_ensure       = $::collectd::params::service_ensure,
  $plugin_dir           = '/usr/local/collectd-plugins/'
) inherits ::collectd::params {

  package{$pkgname:
    ensure => $pkgversion,
    alias  => 'collectd',
  }

  if (($::operatingsystem =~ /(?i:RHEL|CentOS)/ ) and $::lsbmajdistrelease == '5') {

    # Required with a patch to include they Python LDLIB path as documented
    # on  https://github.com/indygreg/collectd-carbon
    file{'/etc/init.d/collectd':
      group  => '0',
      mode   => '0755',
      owner  => '0',
      source => 'puppet:///modules/collectd/collectd',
      before => Service[$service_name],
    }
  }

  file { $plugin_dir:
    ensure => 'directory',
    group  => '0',
    mode   => '0755',
    owner  => '0',
  }

  #if ($::operatingsystem =~ /(?i:Debian|Ubuntu)/ ) {
    # We need a config file that is actually including "/etc/collectd.d" files
    # This has been reported in debian, see Debian BTS #690668
    # Some CentOS packages e.g. 5.4.0 also has this problem
    file{$config_file:
      ensure  => present,
      group   => 'root',
      owner   => 'root',
      mode    => '0644',
      content => template($config_template_name),
      before  => Service[$service_name],
      require => Package[$pkgname],
      notify  => Service['collectd'],
    }
  #}

  file{$config_dir:
    ensure  => 'directory',
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    recurse => $purge,
    purge   => $purge,
  }

  service{$service_name:
    ensure  => $service_ensure,
    enable  => $service_enable,
    require => Package[$pkgname],
  }

}
