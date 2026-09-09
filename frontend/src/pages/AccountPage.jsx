import { useOutletContext } from "react-router-dom";
import PageHeader from "../components/common/PageHeader";
import SectionCard from "../components/common/SectionCard";
import { useAuth } from "../auth/AuthProvider";

export default function AccountPage() {
  const { config, loginWithHosted } = useAuth();
  const { profile } = useOutletContext() || {};

  return (
    <div>
      <PageHeader
        title="Account"
        description="Authentication identities are managed by Auth0. This application does not store passwords."
      />
      <SectionCard title="Identity provider">
        <p className="text-sm leading-6 text-ink-muted">
          Email, password recovery, and social connections are handled by Auth0
          Universal Login. Password reset is not implemented in this application.
        </p>
        <dl className="mt-4 grid gap-2 text-sm">
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-faint">Role</dt>
            <dd className="text-ink">{profile?.role || "—"}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-faint">Email</dt>
            <dd className="text-ink">{profile?.email || "—"}</dd>
          </div>
        </dl>
        {config.databaseEnabled ? (
          <button
            type="button"
            className="mt-4 text-sm font-medium text-accent"
            onClick={() => loginWithHosted({ screenHint: "login" })}
          >
            Open Auth0 password recovery
          </button>
        ) : (
          <p className="mt-4 text-xs text-ink-faint">
            Password recovery is available once the Auth0 database connection is enabled.
          </p>
        )}
      </SectionCard>
    </div>
  );
}
