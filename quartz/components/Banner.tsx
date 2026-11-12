import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import { FilePath, joinSegments, pathToRoot, slugifyFilePath } from "../util/path"

// Shows the Pixel Banner fields from the Obsidian notes (banner, banner-height,
// banner-x, banner-y, icon-image). Every image lives in the content "Images" folder.
function imageUrl(slug: string, value: unknown): string | null {
  if (typeof value !== "string") return null
  const name = value.replace(/^!?\[\[/, "").replace(/(\|[^\]]*)?\]\]$/, "").trim()
  if (!name) return null
  const file = slugifyFilePath(joinSegments("Images", name) as FilePath)
  return joinSegments(pathToRoot(slug as any), file)
}

const Banner: QuartzComponent = ({ fileData }: QuartzComponentProps) => {
  const fm = (fileData.frontmatter ?? {}) as Record<string, unknown>
  const slug = fileData.slug!
  const banner = imageUrl(slug, fm["banner"])
  if (!banner) return null
  const icon = imageUrl(slug, fm["icon-image"])
  const height = Number(fm["banner-height"] ?? 330)
  const x = Number(fm["banner-x"] ?? 50)
  const y = Number(fm["banner-y"] ?? 50)
  return (
    <div class="note-banner" style={`height:${height}px`}>
      <img src={banner} alt="" style={`object-position:${x}% ${y}%`} />
      {icon && <img class="note-banner-icon" src={icon} alt="" />}
    </div>
  )
}

Banner.css = `
.note-banner {
  position: relative;
  margin: 1rem 0 3rem 0;
}
.note-banner > img:first-child {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 17px;
  margin: 0;
  -webkit-mask-image: linear-gradient(to bottom, black 65%, transparent 100%);
  mask-image: linear-gradient(to bottom, black 65%, transparent 100%);
}
.note-banner-icon {
  position: absolute;
  left: 1rem;
  bottom: -2rem;
  width: 90px;
  height: 90px;
  object-fit: cover;
  border-radius: 17px;
  margin: 0;
  border: 3px solid var(--light);
}
`

export default (() => Banner) satisfies QuartzComponentConstructor
