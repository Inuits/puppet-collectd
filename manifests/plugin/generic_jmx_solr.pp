class collectd::plugin::generic_jmx_solr(
  $domain  = "solr/",
  $engine  = "tomcat",
){

  file { '/etc/collectd.d/generic_jmx_solr.conf':
    ensure  => 'file',
    group   => 'root',
    mode    => '0644',
    owner   => 'root',
    content => template('collectd/generic_jmx_solr.conf.erb'),
    notify  => Service['collectd'],
  }
 

  file_line { 
    'custom.types.db-errors':
      path    => '/usr/share/collectd/types.db',
      line    => 'errors		value:GAUGE:0:U', 
      require => Package['collectd'],
      notify  => Service['collectd'];
   'custom.types.db-timeouts':
      path    => '/usr/share/collectd/types.db',
      line    => 'timeouts		value:GAUGE:0:U', 
      require => Package['collectd'],
      notify  => Service['collectd'];
   'custom.types.db-hits':
      path    => '/usr/share/collectd/types.db',
      line    => 'hits		value:GAUGE:0:U', 
      require => Package['collectd'],
      notify  => Service['collectd'];
   'custom.types.db-hitratio':
      path    => '/usr/share/collectd/types.db',
      line    => 'hitratio		value:GAUGE:0:U', 
      require => Package['collectd'],
      notify  => Service['collectd'];
   'custom.types.db-evictions':
      path    => '/usr/share/collectd/types.db',
      line    => 'evictions		value:GAUGE:0:U', 
      require => Package['collectd'],
      notify  => Service['collectd'];
   'custom.types.db-lookups':
      path    => '/usr/share/collectd/types.db',
      line    => 'lookups		value:GAUGE:0:U', 
      require => Package['collectd'],
      notify  => Service['collectd'];
   'custom.types.db-inserts':
      path    => '/usr/share/collectd/types.db',
      line    => 'inserts		value:GAUGE:0:U', 
      require => Package['collectd'],
      notify  => Service['collectd'];
   'custom.types.db-jmx_memory':
      path    => '/usr/share/collectd/types.db',
      line    => 'jmx_memory		value:GAUGE:0:U',
      require => Package['collectd'],
      notify  => Service['collectd'];
   } 
 }