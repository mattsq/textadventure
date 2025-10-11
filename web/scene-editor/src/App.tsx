import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import SceneEditorLayout from "./routes/SceneEditorLayout";
import OverviewPage from "./pages/OverviewPage";
import SceneLibraryPage from "./pages/SceneLibraryPage";
import SceneGraphPage from "./pages/SceneGraphPage";
import SceneCreatePlaceholderPage from "./pages/SceneCreatePlaceholderPage";
import SceneDetailsPage from "./pages/SceneDetailsPage";

export const App: React.FC = () => (
  <BrowserRouter>
    <Routes>
      <Route element={<SceneEditorLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="scenes" element={<SceneLibraryPage />} />
        <Route path="graph" element={<SceneGraphPage />} />
        <Route path="scenes/new" element={<SceneCreatePlaceholderPage />} />
        <Route path="scenes/:sceneId" element={<SceneDetailsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  </BrowserRouter>
);

export default App;
