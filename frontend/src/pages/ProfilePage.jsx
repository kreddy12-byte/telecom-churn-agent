import { useOutletContext } from "react-router-dom";
import PageHeader from "../components/common/PageHeader";
import SectionCard from "../components/common/SectionCard";
import { useAuth } from "../auth/AuthProvider";

export default function ProfilePage() {
  const { user } = useAuth();
  const { profile } = useOutletContext() || {};
  const name = profile?.name || user?.name || "—";
  const email = profile?.email || user?.email || "—";
  const role = profile?.role || "—";
  const picture = profile?.picture || user?.picture;
  const sub = profile?.sub || user?.sub || "—";

  return (
    <div>
      <PageHeader
        title="Profile"
        description="Identity from the verified Auth0 session. Roles are enforced by the API, not by this page."
      />
      <SectionCard title="Signed-in user">
        <div className="flex items-start gap-4">
          {picture ? (
            <img
              src={picture}
              alt=""
              className="h-12 w-12 rounded-full object-cover"
              referrerPolicy="no-referrer"
            />
          ) : null}
          <dl className="grid gap-2 text-sm">
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-faint">Name</dt>
              <dd className="text-ink">{name}</dd>
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-faint">Email</dt>
              <dd className="text-ink">{email}</dd>
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-faint">Role</dt>
              <dd className="text-ink">{role}</dd>
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-faint">Subject</dt>
              <dd className="font-mono text-xs text-ink-muted">{sub}</dd>
            </div>
          </dl>
        </div>
      </SectionCard>
    </div>
  );
}
