/**
 * Broker-facing labels for the enum-valued profile facts the chat captures.
 * Keys mirror the values in `backend/app/services/question_plan.py`.
 * Shared by the qualification checklist and the Edit dialog's selects.
 */

export const INSURANCE_TYPE_LABEL: Record<string, string> = {
  health: 'Health',
  life_term: 'Term life',
  life_whole: 'Whole life',
  investment_linked: 'Investment-linked',
  motor: 'Motor',
  home: 'Home',
  travel: 'Travel',
  multiple: 'Multiple products',
  other: 'Other',
}

export const INTENT_LABEL: Record<string, string> = {
  new_policy: 'New policy',
  review_existing: 'Review / renewal',
  claim_help: 'Claim help',
  other: 'Other',
}

export const TIMELINE_LABEL: Record<string, string> = {
  now: 'Now',
  lt_3mo: 'Within 3 months',
  gt_3mo: 'Later than 3 months',
  undecided: 'Undecided',
}

export const INCOME_BAND_LABEL: Record<string, string> = {
  '<5L': 'Under ₹5L',
  '5-15L': '₹5–15L',
  '15-30L': '₹15–30L',
  '>30L': 'Over ₹30L',
}

/** Label lookup by profile key, for values that come from a fixed set. */
export const VALUE_LABEL: Record<string, Record<string, string>> = {
  insurance_type: INSURANCE_TYPE_LABEL,
  intent: INTENT_LABEL,
  timeline: TIMELINE_LABEL,
  income_band: INCOME_BAND_LABEL,
}
