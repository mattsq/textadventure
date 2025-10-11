import React from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  EditorHeader,
  EditorShell,
  EditorSidebar,
  type EditorSidebarSection,
} from "../components/layout";
import { Breadcrumbs, type BreadcrumbItem } from "../components/navigation";
import { useSceneEditorStore } from "../state";

const onboardingSections: EditorSidebarSection[] = [
  {
    title: "Quick Start",
    content: (
      <ul className="space-y-2">
        <li className="flex items-center gap-2">
          <span className="inline-flex h-2 w-2 rounded-full bg-editor-accent" aria-hidden />
          Launch the Vite dev server.
        </li>
        <li className="flex items-center gap-2">
          <span className="inline-flex h-2 w-2 rounded-full bg-sky-400" aria-hidden />
          Explore placeholder routes to validate layout primitives.
        </li>
      </ul>
    ),
  },
  {
    title: "Upcoming Tasks",
    content: (
      <ul className="space-y-2 text-xs leading-relaxed text-slate-300">
        <li>Add routing to support dedicated list and detail screens.</li>
        <li>Introduce live validation callouts within the inspector.</li>
        <li>Prototype collaborative presence indicators for editors.</li>
      </ul>
    ),
  },
];

const navigationLinks = [
  { to: "/", label: "Overview" },
  { to: "/scenes", label: "Scene Library" },
  { to: "/graph", label: "Scene Graph" },
  { to: "/scenes/new", label: "Create Scene" },
] as const;

const getRouteMetadata = (pathname: string) => {
  if (pathname === "/") {
    return {
      currentLabel: "Scene Editor",
      subtitle: (
        <span>
          Welcome to the browser-based authoring environment for text adventures. Use the navigation to explore
          upcoming editor surfaces as they come online.
        </span>
      ),
      logMessage: "Overview ready to highlight editor roadmap and onboarding guidance.",
    };
  }

  if (pathname === "/scenes") {
    return {
      currentLabel: "Scene Library",
      subtitle: (
        <span>
          Browse the existing scene catalogue, review validation summaries, and prepare for richer editing flows.
        </span>
      ),
      logMessage: "Scene library view focused on dataset summaries and validation readiness.",
    };
  }

  if (pathname === "/scenes/new") {
    return {
      currentLabel: "Create Scene",
      subtitle: (
        <span>
          Draft a new scene using upcoming templates and guided workflows that streamline branching narrative setup.
        </span>
      ),
      logMessage: "New scene workflow staged for future template-driven authoring.",
    };
  }

  if (pathname === "/graph") {
    return {
      currentLabel: "Scene Graph",
      subtitle: (
        <span>
          Explore the connectivity map for the adventure to understand branching flow, terminal paths,
          and upcoming validation overlays.
        </span>
      ),
      logMessage: "Scene graph visualisation ready for topology reviews and validation planning.",
    };
  }

  const match = pathname.match(/^\/scenes\/(.+)$/);
  if (match) {
    const sceneId = decodeURIComponent(match[1]);
    return {
      currentLabel: `Scene: ${sceneId}`,
      subtitle: (
        <span>
          Inspect the selected scene to prepare for detailed editing, validation feedback, and collaborative annotations.
        </span>
      ),
      logMessage: `Focused on scene ${sceneId} for detailed review.`,
      sceneId,
    };
  }

  return {
    currentLabel: "Scene Editor",
    subtitle: <span>Navigate the editor to access project dashboards and authoring tools.</span>,
    logMessage: "Navigated to an experimental route within the editor shell.",
  };
};

export const SceneEditorLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const navigationLog = useSceneEditorStore((state) => state.navigationLog);
  const setNavigationLog = useSceneEditorStore((state) => state.setNavigationLog);

  const { currentLabel, subtitle, logMessage, sceneId } = React.useMemo(
    () => getRouteMetadata(location.pathname),
    [location.pathname],
  );

  React.useEffect(() => {
    setNavigationLog(logMessage);
  }, [logMessage, setNavigationLog]);

  const breadcrumbItems = React.useMemo(() => {
    const items: BreadcrumbItem[] = [
      {
        id: "workspace",
        label: "Workspace",
        onClick: () => navigate("/"),
      },
      {
        id: "project",
        label: "Demo Adventure",
        onClick: () => navigate("/"),
      },
      {
        id: "scene-editor",
        label: "Scene Editor",
        onClick: () => navigate("/"),
        current: location.pathname === "/",
      },
    ];

    if (location.pathname === "/scenes") {
      items.push({ id: "scene-library", label: "Scene Library", current: true });
    } else if (location.pathname === "/scenes/new") {
      items.push({ id: "scene-library", label: "Scene Library", onClick: () => navigate("/scenes") });
      items.push({ id: "scene-create", label: "Create Scene", current: true });
    } else if (location.pathname === "/graph") {
      items.push({ id: "scene-graph", label: "Scene Graph", current: true });
    } else if (sceneId) {
      items.push({ id: "scene-library", label: "Scene Library", onClick: () => navigate("/scenes") });
      items.push({ id: "scene-detail", label: sceneId, current: true });
    }

    return items;
  }, [location.pathname, navigate, sceneId]);

  return (
    <EditorShell
      header={
        <EditorHeader
          badge="Priority 10 Roadmap"
          title={currentLabel}
          subtitle={
            <div className="flex flex-col gap-3">
              <Breadcrumbs items={breadcrumbItems} ariaLabel="Scene editor navigation trail" />
              {subtitle}
            </div>
          }
          actions={
            <nav className="flex items-center gap-2 text-xs">
              {navigationLinks.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  className={({ isActive }) =>
                    [
                      "inline-flex items-center justify-center rounded-md border px-3 py-1.5 font-semibold transition",
                      isActive
                        ? "border-indigo-400/70 bg-indigo-500/30 text-indigo-100"
                        : "border-slate-700 bg-slate-900/60 text-slate-300 hover:border-indigo-400/50 hover:text-indigo-100",
                    ].join(" ")
                  }
                >
                  {link.label}
                </NavLink>
              ))}
            </nav>
          }
        />
      }
      sidebar={<EditorSidebar title="Editor Overview" sections={onboardingSections} footer="Layout components now live." />}
      footer="Tailwind CSS utility classes power the shared layout components."
    >
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <p className="text-xs text-slate-400 md:text-sm">{navigationLog}</p>
        <Outlet />
      </div>
    </EditorShell>
  );
};

export default SceneEditorLayout;
