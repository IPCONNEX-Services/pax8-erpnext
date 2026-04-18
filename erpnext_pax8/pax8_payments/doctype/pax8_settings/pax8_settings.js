frappe.ui.form.on("Pax8 Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Sync Companies"), () => {
			frappe.call({
				method: "erpnext_pax8.api.sync.sync_companies",
				args: { pax8_settings: frm.doc.name },
				freeze: true,
				freeze_message: __("Syncing companies from Pax8..."),
				callback(r) {
					if (r.message) {
						const { matched, unmatched, created } = r.message;
						frappe.msgprint(
							__("Sync complete: {0} matched, {1} unmatched, {2} new.", [matched, unmatched, created])
						);
						frm.reload_doc();
					}
				},
			});
		});

		frm.add_custom_button(__("Register Webhook"), () => {
			frappe.confirm(
				__("Register the INVOICE.CREATED webhook with Pax8? This will overwrite any existing webhook for this endpoint."),
				() => {
					frappe.call({
						method: "erpnext_pax8.api.webhook.register_webhook",
						args: { pax8_settings: frm.doc.name },
						freeze: true,
						freeze_message: __("Registering webhook with Pax8..."),
						callback(r) {
							if (r.message) {
								frappe.msgprint(
									__("Webhook registered. Endpoint: {0}", [r.message.endpoint_url])
								);
								frm.reload_doc();
							}
						},
					});
				}
			);
		});

		frm.add_custom_button(__("Import Month"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Import Billing Period"),
				fields: [
					{
						fieldname: "billing_period",
						fieldtype: "Data",
						label: __("Billing Period (YYYY-MM)"),
						reqd: 1,
						default: frappe.datetime.get_today().substring(0, 7),
						description: __("e.g. 2026-03 — imports the previous month by default"),
					},
				],
				primary_action_label: __("Import"),
				primary_action({ billing_period }) {
					d.hide();
					frappe.call({
						method: "erpnext_pax8.api.import_invoices.import_period",
						args: {
							pax8_settings: frm.doc.name,
							billing_period,
							triggered_by: "manual",
						},
						freeze: true,
						freeze_message: __("Importing Pax8 invoices..."),
						callback(r) {
							if (r.message) {
								const m = r.message;
								frappe.msgprint(
									__("Import {0}: {1} Sales Invoices created, {2} unmatched. Log: {3}", [
										m.status,
										m.sales_invoices_created,
										m.customers_unmatched,
										`<a href="/app/pax8-import-log/${m.log}">${m.log}</a>`,
									])
								);
								frm.reload_doc();
							}
						},
					});
				},
			});
			d.show();
		});
	},
});
