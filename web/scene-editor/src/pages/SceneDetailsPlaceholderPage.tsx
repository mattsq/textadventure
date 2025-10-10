import React from "react";
import { useParams } from "react-router-dom";
import { EditorPanel } from "../components/layout";
import { Badge } from "../components/display";

export const SceneDetailsPlaceholderPage: React.FC = () => {
  const params = useParams<{ sceneId: string }>();
  const sceneId = params.sceneId ? decodeURIComponent(params.sceneId) : "Unknown scene";

  return (
    <EditorPanel
      title={`Scene detail: ${sceneId}`}
      description="Future iterations will provide a fully featured editing form with validation and live previews."
    >
      <div className="flex flex-col gap-4 text-sm text-slate-200 md:text-base">
        <p>
          This placeholder demonstrates that deep links to individual scenes resolve within the new routing system. When
          the detailed editor arrives, authors will be able to modify narration, branching choices, and validation
          settings from this screen.
        </p>
        <p className="text-slate-300">
          Upcoming enhancements will reuse the shared form primitives, introduce auto-save, and stream validation
          results from the backend API in real time.
        </p>
        <Badge variant="info" size="sm" className="self-start">
          Routing Prototype
        </Badge>
      </div>
    </EditorPanel>
  );
};

export default SceneDetailsPlaceholderPage;
