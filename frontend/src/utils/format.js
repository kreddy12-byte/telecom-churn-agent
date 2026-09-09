// Display helpers. These format values; they never invent them.

export function formatPercent(probability) {
  if (probability == null || Number.isNaN(Number(probability))) {
    return "—";
  }
  return `${(Number(probability) * 100).toFixed(2)}%`;
}

export function formatCount(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toLocaleString("en-US");
}

export function formatShare(count, total) {
  if (count == null || !total || Number.isNaN(Number(total))) {
    return "—";
  }
  return `${((Number(count) / Number(total)) * 100).toFixed(1)}%`;
}

export function formatPoints(change) {
  if (change == null || Number.isNaN(Number(change))) {
    return "—";
  }
  const points = Number(change) * 100;
  const sign = points > 0 ? "+" : "";
  return `${sign}${points.toFixed(2)} pp`;
}

export function formatShap(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "—";
  }
  const number = Number(value);
  const sign = number > 0 ? "+" : "";
  return `${sign}${number.toFixed(4)}`;
}

export function formatMoney(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatDate(value) {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function strategyLabel(strategyId) {
  if (!strategyId) {
    return "—";
  }
  return strategyId
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatPageRange(total, offset, pageSize) {
  const safeTotal = Number(total) || 0;
  if (safeTotal <= 0) {
    return "0 of 0";
  }
  const start = Number(offset) || 0;
  const size = Number(pageSize) || 0;
  const first = start + 1;
  const last = Math.min(start + size, safeTotal);
  return `${first}–${last} of ${safeTotal}`;
}

export function featureLabel(name) {
  if (!name) {
    return "—";
  }
  const known = {
    MonthlyCharges: "Monthly Charges",
    TotalCharges: "Total Charges",
    InternetService: "Internet Service",
    PaymentMethod: "Payment Method",
    TechSupport: "Tech Support",
    OnlineSecurity: "Online Security",
    OnlineBackup: "Online Backup",
    DeviceProtection: "Device Protection",
    PaperlessBilling: "Paperless Billing",
    PhoneService: "Phone Service",
    MultipleLines: "Multiple Lines",
    StreamingTV: "Streaming TV",
    StreamingMovies: "Streaming Movies",
    SeniorCitizen: "Senior Citizen",
    Contract: "Contract Type",
    tenure: "Tenure",
  };
  if (known[name]) {
    return known[name];
  }
  return String(name)
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
