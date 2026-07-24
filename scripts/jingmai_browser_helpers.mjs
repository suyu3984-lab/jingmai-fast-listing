/**
 * Small deterministic helpers for Jingmai Chrome runs.
 * The caller still obtains locators from the latest visible DOM snapshot.
 */

const ALLOWED_HOST_SUFFIXES = [".jd.com", ".jcloud.com"];

export function isAllowedSellerUrl(value) {
  try {
    const url = new URL(String(value));
    return (
      url.protocol === "https:" &&
      ALLOWED_HOST_SUFFIXES.some((suffix) => url.hostname === suffix.slice(1) || url.hostname.endsWith(suffix))
    );
  } catch {
    return false;
  }
}

export function discoverOneNewTab(beforeTabs, afterTabs) {
  const beforeIds = new Set((beforeTabs || []).map((tab) => String(tab.id)));
  const created = (afterTabs || []).filter((tab) => !beforeIds.has(String(tab.id)));
  if (created.length !== 1) {
    throw new Error(`expected exactly one new tab, found ${created.length}`);
  }
  if (!isAllowedSellerUrl(created[0].url || "")) {
    throw new Error("new tab is not on an allowed JD seller host");
  }
  return created[0];
}

export async function requireUnique(locator, label) {
  const count = await locator.count();
  if (count !== 1) {
    throw new Error(`${label} must resolve to exactly one element; found ${count}`);
  }
  return locator;
}

export async function readControlState(locator, label) {
  await requireUnique(locator, label);
  return locator.evaluate((element) => ({
    tag: element.tagName,
    value: "value" in element ? element.value : null,
    checked: "checked" in element ? Boolean(element.checked) : null,
    text: (element.textContent || "").trim(),
    disabled: "disabled" in element ? Boolean(element.disabled) : false,
  }));
}

export function buildPageProfile({ url, snapshot, anchors }) {
  if (!isAllowedSellerUrl(url)) {
    throw new Error("cannot profile a non-JD seller page");
  }
  const normalized = String(snapshot || "").replace(/\s+/g, " ");
  const anchorState = (anchors || []).map((anchor) => ({
    anchor,
    present: normalized.includes(String(anchor)),
  }));
  const routeFamily = new URL(url).pathname
    .replace(/\/\d{6,}/g, "/:id")
    .replace(/\/+/g, "/");
  const signature = `${routeFamily}|${anchorState.map((item) => `${item.anchor}:${item.present ? 1 : 0}`).join("|")}`;
  let hash = 2166136261;
  for (let index = 0; index < signature.length; index += 1) {
    hash ^= signature.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return {
    version: 1,
    routeFamily,
    anchors: anchorState,
    fingerprint: `jm-${(hash >>> 0).toString(16).padStart(8, "0")}`,
    allAnchorsPresent: anchorState.every((item) => item.present),
  };
}

export function recommendExecutionMode({ profile, storedFingerprint, recoveryState }) {
  if (recoveryState === "submission_unknown" || recoveryState === "network_interrupted") {
    return "safe";
  }
  if (!profile?.allAnchorsPresent) {
    return "safe";
  }
  return profile.fingerprint === storedFingerprint ? "fast" : "safe";
}

export function assertGate({ returnPolicy, invoiceRestricted, expectedReturnPolicy }) {
  const errors = [];
  if (returnPolicy?.value !== expectedReturnPolicy && returnPolicy?.text !== expectedReturnPolicy) {
    errors.push(`return policy is not ${expectedReturnPolicy}`);
  }
  if (invoiceRestricted?.checked !== true) {
    errors.push("special VAT invoice restriction is not checked");
  }
  if (errors.length) {
    throw new Error(errors.join("; "));
  }
  return { passed: true, checkedAt: new Date().toISOString() };
}
