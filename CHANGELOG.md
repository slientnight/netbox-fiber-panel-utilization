# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-03

### Added
- Device page utilization widget (right sidebar) with color-coded progress bar
- Dedicated detail page at `/plugins/fiber-patch-panel-utilization/<device_id>/`
- REST API endpoint at `/api/plugins/fiber-panel-utilization/panels/<device_id>/utilization/`
- Configurable device qualification via `device_type_slugs`, `device_role_slugs`, and `model_regex`
- Structural detection fallback when no filters are configured
- Per-module utilization breakdown with mini progress bars
- Front port table on detail page with connection status and far-end info
- Configurable warning/critical color thresholds
- Toggle options for module breakdown and port table display
- Empty state messages for devices with no modules or no front ports
- Error handling with user-friendly messages
- 171 tests including unit, property-based (Hypothesis), and integration tests
