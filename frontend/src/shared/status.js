export const FLOW = [
  "new", "invited", "walkthru_initiated", "walkthru_completed",
  "quote_generated", "contract_sent", "pending_deposit", "deposit_received",
];

export const STATUS = {
  new: { label: "New", bg: "#EEF0F3", fg: "#3B4351" },
  invited: { label: "Invited", bg: "#E6EEFB", fg: "#1E3A8A" },
  walkthru_initiated: { label: "Walkthru initiated", bg: "#D6E4FB", fg: "#17327A" },
  walkthru_completed: { label: "Walkthru completed", bg: "#FDF0D2", fg: "#7A4A00" },
  quote_generated: { label: "Quote generated", bg: "#FBE3D3", fg: "#8A2F0B" },
  contract_sent: { label: "Contract sent", bg: "#E4DDF7", fg: "#3F2A8C" },
  pending_deposit: { label: "Pending deposit", bg: "#D9F0EB", fg: "#0B5F55" },
  deposit_received: { label: "Deposit received", bg: "#0F766E", fg: "#FFFFFF" },
  dropped: { label: "Dropped", bg: "#F3E3E3", fg: "#7F1D1D" },
};

export const JOURNEY = {
  new: "Lead received",
  invited: "Text sent, link opened",
  walkthru_initiated: "Agent walkthru initiated",
  walkthru_completed: "Walkthru completed",
  quote_generated: "Quote generated",
  contract_sent: "Quote accepted, contract sent",
  pending_deposit: "Contract executed, pending deposit",
  deposit_received: "Deposit received",
};

export const ACTIVITY = {
  new: "Lead received",
  invited: "Text sent",
  walkthru_completed: "Call ended",
  quote_generated: "Quote sent",
  contract_sent: "Quote accepted",
  pending_deposit: "Contract signed",
  deposit_received: "Deposit paid",
  dropped: "Dropped",
};

export const SOURCES = {
  thumbtack: "Thumbtack", handy: "Handy", angi: "Angi", website: "Website", referral: "Referral",
};
