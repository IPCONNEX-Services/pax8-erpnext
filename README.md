# Pax8 for ERPNext

A Frappe app to import Pax8 monthly invoices into ERPNext as Purchase and Sales Invoices.

## Features

- Import vendor invoices from Pax8 as ERPNext Purchase Invoices
- Import resale invoices from Pax8 as ERPNext Sales Invoices
- Scheduled daily sync with automatic import logic
- Prevent duplicate invoices with import logging

## Installation

```bash
bench get-app pax8-erpnext https://github.com/IPCONNEX-Services/pax8-erpnext
bench --site [your-site] install-app erpnext_pax8
```

## Configuration

1. Navigate to Pax8 Settings in your ERPNext desk
2. Enter your Pax8 API credentials (available via Infisical)
3. Configure month boundaries and invoice thresholds

## License

MIT
