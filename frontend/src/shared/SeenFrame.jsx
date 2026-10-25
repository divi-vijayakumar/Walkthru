import { useState } from "react";
import { Camera } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

export const SeenFrame = ({ item }) => {
  const [open, setOpen] = useState(false);
  const ev = item.evidence || {};
  if (item.basis !== "seen" || !ev.frame_url) return null;
  const box = ev.box;
  return (
    <>
      <button type="button" data-testid={`seen-frame-btn-${item.key}`} aria-label="See what the camera saw" onClick={() => setOpen(true)}
        className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[#CCFBF1] text-wt-teal transition-transform duration-150 hover:scale-110">
        <Camera className="h-4 w-4" />
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid={`seen-frame-dialog-${item.key}`} className="max-w-lg bg-white">
          <DialogTitle>{item.label}</DialogTitle>
          <DialogDescription>What the camera saw{ev.label ? `: ${ev.label.split(":").pop().trim()}` : ""}</DialogDescription>
          <div className="relative mx-auto w-fit overflow-hidden rounded-xl">
            <img data-testid={`seen-frame-img-${item.key}`} src={ev.frame_url} alt={`Camera frame for ${item.label}`} className="block max-h-[70vh] w-auto" />
            {Array.isArray(box) && box.length === 4 && (
              <span className="pointer-events-none absolute rounded-md border-[3px] border-[#F97316]"
                style={{ left: `${box[0] * 100}%`, top: `${box[1] * 100}%`, width: `${box[2] * 100}%`, height: `${box[3] * 100}%` }} />
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
