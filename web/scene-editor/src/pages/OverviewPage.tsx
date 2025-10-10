import React from "react";
import { EditorPanel } from "../components/layout";
import { Badge, Card } from "../components/display";

export const OverviewPage: React.FC = () => (
  <>
    <EditorPanel
      title="Editor Roadmap"
      description="High-level summary of the upcoming browser-based authoring experience."
    >
      <p>
        The scene editor will evolve into a collaborative environment for designing adventures, orchestrating validation
        checks, and streaming live playtests. Each milestone expands on these foundations with richer data views,
        multi-agent tooling, and guided authoring workflows.
      </p>
    </EditorPanel>
    <EditorPanel
      title="Planned Milestones"
      variant="subtle"
      description="Track the sequence of enhancements driving the scene editor initiative."
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Card
          title="Routing"
          description="Dedicated URLs for core editor flows unlock bookmarking and deep linking."
          actions={<Badge size="sm" variant="info">In Progress</Badge>}
        >
          <p className="text-slate-300">
            Phase 2 introduces a routing system to separate the overview, scene library, and detailed editing screens.
            Future updates will expand this to analytics dashboards and collaborative tooling.
          </p>
        </Card>
        <Card
          title="Scene Authoring"
          description="Interactive forms for editing scene metadata, choices, and transitions."
          actions={<Badge size="sm">Planned</Badge>}
        >
          <p className="text-slate-300">
            Structured forms and inline validation feedback will streamline authoring workflows, reducing the need to
            hand-edit JSON while ensuring data integrity.
          </p>
        </Card>
        <Card
          title="Live Playtesting"
          description="Embed the runtime to play through adventures directly in the browser."
          actions={<Badge size="sm" variant="warning">Upcoming</Badge>}
        >
          <p className="text-slate-300">
            Coordinated test sessions will surface transcript logs, memory snapshots, and branching analytics in real
            time as authors iterate on their stories.
          </p>
        </Card>
        <Card
          title="Collaboration"
          description="Presence indicators and review workflows for distributed teams."
          actions={<Badge size="sm" variant="neutral">Future</Badge>}
        >
          <p className="text-slate-300">
            Shared activity feeds, review requests, and version timelines will help teams coordinate changes across
            large adventures.
          </p>
        </Card>
      </div>
    </EditorPanel>
  </>
);

export default OverviewPage;
