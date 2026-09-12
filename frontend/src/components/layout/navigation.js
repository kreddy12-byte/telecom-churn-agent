/** Application shell navigation — only real routes. */

export const PRODUCT = {
  name: "Churn Intelligence",
  descriptor: "Customer risk platform",
  markLabel: "CI",
};

export const PRIMARY_NAV = [
  {
    to: "/",
    label: "Overview",
    end: true,
    icon: "overview",
  },
  {
    to: "/customers",
    label: "Customer Intelligence",
    end: false,
    icon: "customers",
    match: (pathname) => pathname === "/customers" || pathname.startsWith("/customers/"),
  },
  {
    to: "/actions",
    label: "Retention Actions",
    end: true,
    icon: "actions",
  },
  {
    to: "/batch",
    label: "Batch Analysis",
    end: true,
    icon: "batch",
  },
];

export const SYSTEM_NAV = [
  {
    to: "/model",
    label: "Model Intelligence",
    end: true,
    icon: "model",
  },
  {
    to: "/account",
    label: "Account",
    end: true,
    icon: "account",
  },
];

const ROUTE_CRUMBS = [
  { test: (p) => p === "/", items: [{ label: "Overview" }] },
  {
    test: (p) => /^\/customers\/[^/]+$/.test(p),
    items: (p) => [
      { label: "Customer Intelligence", to: "/customers" },
      { label: decodeURIComponent(p.split("/")[2] || "Customer") },
    ],
  },
  { test: (p) => p === "/customers", items: [{ label: "Customer Intelligence" }] },
  { test: (p) => p === "/actions", items: [{ label: "Retention Actions" }] },
  { test: (p) => p === "/batch", items: [{ label: "Batch Analysis" }] },
  { test: (p) => p === "/model", items: [{ label: "Model Intelligence" }] },
  { test: (p) => p === "/profile", items: [{ label: "Profile" }] },
  { test: (p) => p === "/account", items: [{ label: "Account" }] },
];

export function breadcrumbsForPath(pathname) {
  for (const route of ROUTE_CRUMBS) {
    if (route.test(pathname)) {
      return typeof route.items === "function" ? route.items(pathname) : route.items;
    }
  }
  return [];
}

export function isNavActive(item, pathname) {
  if (typeof item.match === "function") {
    return item.match(pathname);
  }
  if (item.end) {
    return pathname === item.to;
  }
  return pathname === item.to || pathname.startsWith(`${item.to}/`);
}
