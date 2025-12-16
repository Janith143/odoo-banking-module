/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class BankDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            accountCount: 0,
            totalBalance: 0,
            transactionCount: 0,
            pendingTransfers: 0,
            activeLoans: 0,
            activeFDs: 0,
            loading: true,
        });

        this.loadDashboardData();
    }

    async loadDashboardData() {
        try {
            // Load account statistics
            const accounts = await this.orm.searchRead(
                "bank.account",
                [["status", "=", "active"]],
                ["balance"]
            );

            this.state.accountCount = accounts.length;
            this.state.totalBalance = accounts.reduce((sum, acc) => sum + acc.balance, 0);

            // Load transaction count
            const transactionCount = await this.orm.searchCount(
                "bank.transaction",
                [["status", "=", "completed"]]
            );
            this.state.transactionCount = transactionCount;

            // Load pending transfers
            const pendingTransfers = await this.orm.searchCount(
                "bank.transfer",
                [["status", "=", "pending"]]
            );
            this.state.pendingTransfers = pendingTransfers;

            // Load active loans
            const activeLoans = await this.orm.searchCount(
                "bank.loan",
                [["status", "=", "active"]]
            );
            this.state.activeLoans = activeLoans;

            // Load active FDs
            const activeFDs = await this.orm.searchCount(
                "bank.fixed.deposit",
                [["status", "=", "active"]]
            );
            this.state.activeFDs = activeFDs;

            this.state.loading = false;
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            this.state.loading = false;
        }
    }

    openAccounts() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bank.account",
            views: [[false, "list"], [false, "form"]],
            domain: [["status", "=", "active"]],
        });
    }

    openTransactions() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bank.transaction",
            views: [[false, "list"], [false, "form"]],
        });
    }

    openPendingTransfers() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "bank.transfer",
            views: [[false, "list"], [false, "form"]],
            domain: [["status", "=", "pending"]],
        });
    }
}

BankDashboard.template = "odoo_bank.BankDashboard";

registry.category("actions").add("bank_dashboard", BankDashboard);
