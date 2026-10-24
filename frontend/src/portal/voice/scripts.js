const pick = (text, options, fallback) => options.find((o) => (text || "").toLowerCase().includes(o)) || fallback;
const fmt = (n) => `$${Math.round(n).toLocaleString("en-US")}`;
export const rangeOf = (r) => `${fmt(r.low)} to ${fmt(r.high)}`;
const slug = (s) => s.toLowerCase().replace(/[^a-z]+/g, "_").replace(/^_|_$/g, "");

const bathArgs = (ctx, changes = []) => ({
  project_type: "bathroom_remodel",
  room_size: pick(ctx.user[0], ["small", "medium", "large"], "medium"),
  finish_level: pick(ctx.user[1], ["refresh", "standard", "premium"], "standard"),
  requested_changes: changes,
  known_issues: ctx.user[2] || "",
  timeline: ctx.user[2] || "",
});

const firstBath = (c) => [
  { role: "assistant", text: `Hi ${c.first}, I'm ${c.agent}, the AI estimator for ${c.contractor}. Tell me a bit about the ${c.ask} you have in mind.` },
  { role: "user", text: "It's our main bathroom, about medium sized. There's an old alcove tub, a vinyl floor and a single vanity." },
  { role: "assistant", text: "Thanks. What finish level feels right: a refresh, standard, or premium?" },
  { role: "user", text: "Standard is good. Nothing too fancy." },
  { role: "assistant", text: "Any timeline in mind, or known issues like leaks or soft spots in the floor?" },
  { role: "user", text: "Everything seems solid. We'd like to start in about two months." },
  { role: "assistant", text: (ctx) => { const a = bathArgs(ctx); return `Great. Let me price a ${a.finish_level} package for a ${a.room_size} bath.`; } },
  { tool: "get_quote_estimate", args: (ctx) => bathArgs(ctx) },
  { role: "assistant", text: (ctx) => `Your estimate is ${rangeOf(ctx.last)}. Is there anything you'd like to change?` },
  { role: "user", text: "Actually, a walk-in shower instead of the tub, and I'd love a double vanity if it fits." },
  { role: "assistant", text: "Got it, a walk-in shower with the double vanity. Let me reprice that for you." },
  { tool: "get_quote_estimate", args: (ctx) => bathArgs(ctx, [ctx.lastUser]) },
  { role: "assistant", text: (ctx) => `That comes to ${rangeOf(ctx.last)}. ${c.contractor} confirms the final price after a quick site check. Anything else?` },
  { role: "user", text: "No, that sounds great." },
  { role: "assistant", text: `Perfect. I'll send your quote now. Thanks, ${c.first}!` },
];

const firstOther = (c) => [
  { role: "assistant", text: `Hi ${c.first}, I'm ${c.agent}, the AI estimator for ${c.contractor}. Tell me about the ${c.ask} you have in mind.` },
  { role: "user", text: "We'd like to update the whole space with mid-range finishes and fix a few worn spots." },
  { role: "assistant", text: "Thanks, that's really helpful. Let me check pricing for that." },
  { tool: "get_quote_estimate", args: (ctx) => ({ project_type: slug(c.ask), requested_changes: [ctx.lastUser] }) },
  { role: "assistant", text: (ctx) => `Your estimate is ${rangeOf(ctx.last)}. Thanks, ${c.first}!` },
];

const changeCall = (c) => [
  { role: "assistant", text: (ctx) => `Welcome back, ${c.first}. Your current estimate is ${rangeOf(ctx.quote)}. What would you like to change?` },
  { role: "user", text: "Could we do vinyl plank flooring instead of tile to save a bit?" },
  { tool: "request_adjustment", args: (ctx) => ({ change_type: "scope_change", description: ctx.lastUser }) },
  { role: "assistant", text: (ctx) => `Done. Your estimate is now ${rangeOf(ctx.last)}. Anything else?` },
  { role: "user", text: "If we can sign this week and stay flexible on the start date, is there a discount?" },
  {
    tool: "request_adjustment",
    args: (ctx) => ({
      change_type: "discount_request",
      can_sign_within_7_days: /week|7 days|seven|sign/i.test(ctx.lastUser),
      flexible_timeline_weeks: /flexib/i.test(ctx.lastUser) ? 4 : 0,
    }),
  },
  {
    role: "assistant",
    text: (ctx) => (ctx.last.status === "limit_reached"
      ? `That's the best I can do right now: ${rangeOf(ctx.last)}.`
      : `${ctx.last.say} Your new estimate is ${rangeOf(ctx.last)}.`),
  },
  { role: "user", text: "Great, thank you." },
  { role: "assistant", text: "You're welcome. I'm updating your quote now." },
];

export const buildScript = (c, mode) => {
  if (mode === "change") return changeCall(c);
  return c.ask.toLowerCase().includes("bath") ? firstBath(c) : firstOther(c);
};

export const failureLines = (c, r, hadQuote) => {
  if (hadQuote) return [`I'll flag that change for the ${c.contractor} team. Your current quote stays as it is for now.`];
  if (r.status === "needs_human") {
    return [`This one needs a person to price. I'll have the team at ${c.contractor} put your quote together and text you shortly.`];
  }
  return [`Pricing isn't available right now, so ${c.contractor} will send your quote shortly. Thanks, ${c.first}.`];
};
