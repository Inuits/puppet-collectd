#
class collectd::plugin::write_graphite ( $graphitehost, $graphiteport) {

  file {
    '/etc/collectd.d/write_graphite.conf':
      group   => '0',
      mode    => '0644',
      owner   => '0',
      require => Package['collectd'],
      notify  => Service['collectd'],
      content => template('collectd/plugin/write_graphite.conf.erb');
  }

}
