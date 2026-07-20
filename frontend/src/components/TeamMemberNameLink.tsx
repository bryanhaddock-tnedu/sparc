import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../lib/auth";
import { teamMemberDetailPath, type TeamMemberRouteTarget } from "../lib/routes";

type TeamMemberNameLinkProps = {
  children: ReactNode;
  className?: string;
  linkClassName?: string;
  member: TeamMemberRouteTarget | null | undefined;
  title?: string;
};

export function TeamMemberNameLink({ children, className, linkClassName, member, title }: TeamMemberNameLinkProps) {
  const { status } = useAuth();
  const canViewProfile = status?.capabilities.can_view_team_member_profiles === true;
  if (!canViewProfile || !member || !hasTeamMemberRoute(member)) {
    return (
      <span className={className} title={title}>
        {children}
      </span>
    );
  }
  return (
    <Link className={[className, linkClassName].filter(Boolean).join(" ")} title={title} to={teamMemberDetailPath(member)}>
      {children}
    </Link>
  );
}

function hasTeamMemberRoute(member: TeamMemberRouteTarget) {
  return Boolean(member.slug || member.memberSlug || member.team_member_slug || member.id != null || member.memberId != null || member.team_member_id != null);
}
