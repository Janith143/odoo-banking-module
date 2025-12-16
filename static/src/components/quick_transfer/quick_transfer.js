/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class QuickTransfer extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            fromAccount: null,
            toAccount: null,
            amount: 0,
            description: "",
            accounts: [],
            loading: false,
        });

        this.loadAccounts();
    }

    async loadAccounts() {
        const accounts = await this.orm.searchRead(
            "bank.account",
            [["status", "=", "active"]],
            ["account_number", "account_name", "balance"]
        );
        this.state.accounts = accounts;
    }

    async submitTransfer() {
        if (!this.state.fromAccount || !this.state.toAccount) {
            this.notification.add("Please select both accounts", { type: "warning" });
            return;
        }

        if (this.state.amount <= 0) {
            this.notification.add("Amount must be greater than zero", { type: "warning" });
            return;
        }

        if (this.state.fromAccount === this.state.toAccount) {
            this.notification.add("Cannot transfer to the same account", { type: "warning" });
            return;
        }

        this.state.loading = true;

        try {
            await this.orm.create("bank.transfer", [{
                from_account_id: parseInt(this.state.fromAccount),
                to_account_id: parseInt(this.state.toAccount),
                transfer_type: "internal",
                amount: parseFloat(this.state.amount),
                description: this.state.description,
                status: "draft",
            }]);

            this.notification.add("Transfer created successfully", { type: "success" });

            // Reset form
            this.state.fromAccount = null;
            this.state.toAccount = null;
            this.state.amount = 0;
            this.state.description = "";

        } catch (error) {
            this.notification.add("Error creating transfer: " + error.message, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }
}

QuickTransfer.template = "odoo_bank.QuickTransfer";

registry.category("actions").add("quick_transfer", QuickTransfer);
