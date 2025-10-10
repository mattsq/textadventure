import React from "react";
import { EditorPanel } from "../components/layout";
import { Badge, Card } from "../components/display";

export const SceneCreatePlaceholderPage: React.FC = () => (
  <EditorPanel
    title="Create a new scene"
    description="Template-driven authoring will live here once the guided workflow is implemented."
  >
    <div className="space-y-4 text-sm text-slate-200 md:text-base">
      <p>
        The creation wizard will walk authors through defining high-level metadata, drafting initial narration,
        and configuring branching options. Automated validation will ensure new scenes integrate seamlessly with
        existing adventures.
      </p>
      <Card
        title="Coming soon"
        description="Outline of the planned multi-step workflow."
        actions={<Badge variant="warning" size="sm">In Design</Badge>}
      >
        <ol className="list-decimal space-y-2 pl-5 text-xs text-slate-300 md:text-sm">
          <li>Choose a starting template or copy from an existing scene.</li>
          <li>Provide key metadata such as title, summary, and tags.</li>
          <li>Add initial choices with narration and transition targets.</li>
          <li>Review validation hints before saving to the library.</li>
        </ol>
      </Card>
    </div>
  </EditorPanel>
);

export default SceneCreatePlaceholderPage;
