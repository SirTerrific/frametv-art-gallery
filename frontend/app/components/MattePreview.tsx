import React from "react";
import { MATTE_PADDING, MATTE_SWATCHES } from "../utils/matte";

interface MattePreviewProps {
  src: string;
  alt: string;
  style: string;
  color: string;
}

/**
 * A rough picture of the artwork on the TV: a 16:9 screen, the matte around it, and the
 * image inside. It only helps choose a matte; the TV renders its own, so the colors and
 * proportions here are approximate, and the multi-panel styles are shown as one frame.
 */
const MattePreview: React.FC<MattePreviewProps> = ({ src, alt, style, color }) => {
  const hasMatte = !!style && style !== "none";
  const padding = MATTE_PADDING[style] ?? MATTE_PADDING.modern;
  const background = hasMatte ? MATTE_SWATCHES[color] ?? MATTE_SWATCHES.neutral : "#000000";

  return (
    <figure className="m-0">
      <div
        className="w-full overflow-hidden rounded-md border border-border/60 shadow-sm"
        style={{ aspectRatio: "16 / 9", background, padding }}
        data-testid="matte-preview"
      >
        <div
          className="h-full w-full overflow-hidden"
          // Shadowbox sinks the artwork behind the matte, which an inner shadow suggests.
          style={style === "shadowbox" ? { boxShadow: "inset 0 0 14px rgba(0,0,0,0.45)" } : undefined}
        >
          <img
            src={src}
            alt={alt}
            // Without a matte the TV fills its screen, so the image covers it; inside a
            // matte the whole artwork stays visible.
            className={`h-full w-full ${hasMatte ? "object-contain" : "object-cover"}`}
          />
        </div>
      </div>
      <figcaption className="mt-1 text-center text-[10px] text-muted-foreground">
        Approximate preview. The TV draws its own matte.
      </figcaption>
    </figure>
  );
};

export default MattePreview;
