#pragma once
#include <cmath>

namespace aurora::gx {
struct ProjectionAspectScale { float horizontal = 1.0f, vertical = 1.0f; };

// Preserve geometry and the complete HUD when adapting the game's 16:9 cameras.
// Wider screens gain horizontal view; 16:10 gains vertical view with the same width.
inline ProjectionAspectScale projection_aspect_scale(float source, float target, bool screenSized) {
  if (!screenSized || !std::isfinite(source) || !std::isfinite(target) ||
      source <= 1.68f || source >= 1.88f || target <= 0.0f) return {};
  if (target < source) return {1.0f, target / source};
  return {source / target, 1.0f};
}

// Translate a top-anchored UI group in camera units, preserving its pixel inset
// when a narrower display gains vertical view. Apply to the HUD model matrix,
// not the camera: world geometry and centered dialog boxes must stay centered.
inline float projection_top_anchor_translation(float source, float target, float projectionY, bool screenSized,
                                               float clipW = 1.0f) {
  if (!std::isfinite(projectionY) || projectionY <= 0.0f || !std::isfinite(clipW) || clipW <= 0.0f) return 0.0f;
  const auto scale = projection_aspect_scale(source, target, screenSized);
  return clipW * (1.0f - scale.vertical) / (projectionY * scale.vertical);
}
} // namespace aurora::gx
