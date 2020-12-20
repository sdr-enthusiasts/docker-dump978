# mikenye/dump978

[![GitHub Workflow Status](https://img.shields.io/github/workflow/status/mikenye/docker-dump978/Deploy%20to%20Docker%20Hub)](https://github.com/mikenye/docker-dump978/actions?query=workflow%3A%22Deploy+to+Docker+Hub%22)
[![Docker Pulls](https://img.shields.io/docker/pulls/mikenye/dump978.svg)](https://hub.docker.com/r/mikenye/dump978)
[![Docker Image Size (tag)](https://img.shields.io/docker/image-size/mikenye/dump978/latest)](https://hub.docker.com/r/mikenye/dump978)
[![Discord](https://img.shields.io/discord/734090820684349521)](https://discord.gg/sTf9uYF)

This container provides the FlightAware 978MHz UAT decoder, and the ADSBExchange fork of `uat2esnt`, working together in harmony. A rare example of harmony in these turblent times. :-)

This container can be used alongside [mikenye/readsb-protobuf](https://github.com/mikenye/docker-readsb-protobuf) to provide UAT into several feeders.

This container also contains InfluxData's [Telegraf](https://docs.influxdata.com/telegraf/), and can send flight data and `dump978` metrics to InfluxDB (if wanted - not started by default).

UAT is currently only used in the USA, so don't bother with this if you're not located in the USA.

## Documentation

Please [read this container's detailed and thorough documentation in the GitHub repository.](https://github.com/mikenye/docker-dump978/blob/master/README.md)
