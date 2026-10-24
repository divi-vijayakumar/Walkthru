export const NAV = {
  wordmark: "sidebar-brand-wordmark",
  leadsLink: "sidebar-nav-leads",
  contractorCard: "contractor-profile-card",
  mobileMenu: "mobile-menu-button",
};

export const DASHBOARD = {
  page: "dashboard-page",
  title: "dashboard-title",
  stat: (key) => `dashboard-stat-${key}`,
  table: "leads-table",
  row: (id) => `lead-row-${id}`,
  status: (id) => `lead-status-badge-${id}`,
  loading: "leads-loading",
  error: "leads-error",
};

export const LEAD = {
  page: "lead-detail-page",
  back: "lead-detail-back-link",
  name: "lead-detail-customer-name",
  projectType: "lead-detail-project-type",
  phone: "lead-detail-phone",
  statusSelect: "lead-detail-status-selector",
  statusOption: (s) => `lead-status-option-${s}`,
  video: "lead-detail-video-player",
  notes: "lead-detail-notes",
  messagesPanel: "lead-detail-messages-panel",
  message: (id) => `lead-message-${id}`,
  messageInput: "lead-detail-message-input",
  sendMessage: "lead-detail-send-message-btn",
  scopePanel: "extracted-scope-empty-panel",
  quotePanel: "quote-empty-panel",
  notFound: "lead-detail-not-found",
};
