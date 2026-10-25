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

const REPLIES = {
  replacing_vanity: ["A new floating one, a bit wider.", "new"],
  new_vanity_mount: ["Floating on the wall.", "floating"],
  new_vanity_sinks: ["Just one sink.", "1"],
  sinks: ["It's a single sink.", "1"],
  vanity_mount: ["It sits right on the floor.", "floor"],
  tub_type: ["It's tucked between three walls.", "alcove"],
  cast_iron: ["I don't think it's metal.", "no"],
  shower_size: ["About the same size as the tub.", "standard"],
  shower_glass: ["A glass door, please.", "door"],
  shower_niche: ["Yes, a niche would be great.", "yes"],
  curbless: ["No, a small lip is fine.", "no"],
  finish_level: ["Standard is good.", "standard"],
  water_damage: ["No leaks that we know of.", "no"],
  timeline: ["In about two months.", "in two months"],
  grab_bars: ["Two, please.", "2"],
  bench: ["No bench.", "no"],
  stove_fuel_now: ["It's gas right now.", "gas"],
  stove_fuel_new: ["Keep it gas.", "gas"],
  cabinet_work: ["New cabinets.", "replace"],
  counter_material_new: ["Quartz, please.", "quartz"],
  undermount_sink: ["Yes, under the counter.", "yes"],
};

const firstBath = (c) => [
  { role: "assistant", text: `Hi ${c.first}, I'm ${c.agent}, the AI estimator for ${c.contractor}. Tell me a bit about the ${c.ask} you have in mind.` },
  { role: "user", text: "I want this sink gone, and I'd love a walk-in shower instead of the tub." },
  { scope: { replies: REPLIES } },
  { role: "assistant", text: (ctx) => `That comes to ${rangeOf(ctx.last)}. ${c.contractor} confirms the final price after a quick site check. Anything else?` },
  { role: "user", text: "No, that sounds great." },
  { role: "assistant", text: `Perfect. I'll send your quote now. Thanks, ${c.first}!` },
];

const firstOther = (c) => [
  { role: "assistant", text: `Hi ${c.first}, I'm ${c.agent}, the AI estimator for ${c.contractor}. Tell me about the ${c.ask} you have in mind.` },
  { role: "user", text: "We'd like new cabinets and countertops, and the stove redone." },
  { scope: { replies: REPLIES } },
  { role: "assistant", text: (ctx) => `Your estimate is ${rangeOf(ctx.last)}. Thanks, ${c.first}!` },
];

const changeCall = (c) => [
  { role: "assistant", text: (ctx) => `Welcome back, ${c.first}. Your current estimate is ${rangeOf(ctx.quote)}. What would you like to change?` },
  { role: "user", text: "Could we also add grab bars?" },
  { scope: { replies: REPLIES } },
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
