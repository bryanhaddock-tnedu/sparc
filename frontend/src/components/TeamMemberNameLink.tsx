import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { teamMemberDetailPath, type TeamMemberRouteTarget } from "../lib/routes";

type TeamMemberNameLinkProps = {
  children: ReactNode;
  className?: string;
  member: TeamMemberRouteTarget | null | undefined;
  title?: string;
};

export function TeamMemberNameLink({ children, className, member, title }: TeamMemberNameLinkProps) {
  if (!member || !hasTeamMemberRoute(member)) {
    return (
      <span className={className} title={title}>
        {children}
      </span>
    );
  }
  return (
    <Link className={className} title={title} to={teamMemberDetailPath(member)}>
      {children}
    </Link>
  );
}

function hasTeamMemberRoute(member: TeamMemberRouteTarget) {
  return Boolean(member.slug || member.memberSlug || member.team_member_slug || member.id != null || member.memberId != null || member.team_member_id != null);
}
