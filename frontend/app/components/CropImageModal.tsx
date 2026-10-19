import React, { useEffect, useRef, useState } from "react";
import Cropper from "react-cropper";
import "cropperjs/dist/cropper.css";
import { XMarkIcon } from "@heroicons/react/24/outline";
import { cropImage, getCropPresets, type CropPreset } from "../utils/galleryApi";

interface CropImageModalProps {
  isOpen: boolean;
  imageUrl: string;
  filename: string;
  onClose: () => void;
  onCropSuccess: (newUrl: string) => void;
}

const CropImageModal: React.FC<CropImageModalProps> = ({
  isOpen,
  imageUrl,
  filename,
  onClose,
  onCropSuccess,
}) => {
  const cropperRef = useRef<any>(null);
  const [cropperReady, setCropperReady] = useState(false);
  const [cropPreset, setCropPreset] = useState('');
  const [cropActionLoading, setCropActionLoading] = useState(false);
  const [cropMessage, setCropMessage] = useState('');

  // The backend owns the preset list, so the Frame TV's own 3840x2160 shows up here too.
  const [cropPresets, setCropPresets] = useState<CropPreset[]>([]);
  useEffect(() => {
    if (!isOpen) return;
    getCropPresets().then(setCropPresets).catch(() => setCropPresets([]));
  }, [isOpen]);

  const handleCrop = async () => {
    if (!filename || !cropperRef.current?.cropper) {
      setCropMessage('Cropper not initialized. Open crop dialog and wait.');
      return;
    }

    if (!cropperReady) {
      setCropMessage('Cropper is not ready yet. Please wait a moment.');
      return;
    }

    setCropActionLoading(true);
    setCropMessage('');

    try {
      // Always crop what the box shows, so a preset box the person moved is honoured.
      const { x, y, width, height } = cropperRef.current.cropper.getData(true);
      if (![x, y, width, height].every(Number.isFinite) || width < 1 || height < 1) {
        setCropMessage('Crop coordinates are invalid. Try adjusting the crop area.');
        return;
      }
      const res = await cropImage(filename, Math.max(0, x), Math.max(0, y), width, height);

      if (!res.success) throw new Error((res as any).error || 'Crop failed');

      const cacheBustedUrl = `${imageUrl}${imageUrl.includes('?') ? '&' : '?'}cb=${Date.now()}`;
      setCropMessage('Crop applied successfully.');
      onCropSuccess(cacheBustedUrl);
      onClose();
    } catch (e: any) {
      console.error('Crop error:', e);
      setCropMessage(e.message || 'Failed to crop image');
    } finally {
      setCropActionLoading(false);
    }
  };

  const applyCropPreset = (width: number, height: number) => {
    if (!cropperRef.current?.cropper) return;
    try {
      const cropper = cropperRef.current.cropper;
      cropper.setAspectRatio(width / height);
      const imageData = cropper.getImageData();
      if (!imageData) {
        console.warn('Image data not ready for preset');
        return;
      }
      const left = Math.max(0, (imageData.naturalWidth - width) / 2);
      const top = Math.max(0, (imageData.naturalHeight - height) / 2);
      
      cropper.setData({
        x: left,
        y: top,
        width: width,
        height: height
      });
      console.log('Preset applied:', { width, height, left, top });
    } catch (e: any) {
      console.warn('Failed to apply preset:', e);
    }
  };

  const handleClose = () => {
    setCropperReady(false);
    setCropMessage('');
    setCropPreset('');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-4xl rounded-lg bg-card shadow-lg overflow-hidden">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-lg font-semibold">Crop Image: {filename}</h3>
          <button onClick={handleClose} className="text-foreground hover:text-black">
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 p-4">
          <div className="rounded overflow-hidden border" style={{ height: 350 }}>
            <Cropper
              src={imageUrl}
              style={{ height: "100%", width: "100%" }}
              aspectRatio={16 / 9}
              guides={true}
              viewMode={1}
              background={false}
              zoomable={true}
              responsive={true}
              autoCropArea={0.9}
              checkOrientation={false}
              ready={() => {
                console.log('Cropper is ready');
                setCropperReady(true);
              }}
              ref={cropperRef}
            />
          </div>

          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-sm font-medium">Presets</label>
              <select
                value={cropPreset}
                onChange={e => {
                  const selected = cropPresets.find(p => p.id === e.target.value);
                  setCropPreset(e.target.value);
                  if (selected) {
                    applyCropPreset(selected.width, selected.height);
                  } else {
                    cropperRef.current?.cropper?.setAspectRatio(16 / 9);
                  }
                }}
                className="w-full border rounded px-2 py-1"
              >
                <option value="">Free 16:9 (fills a Frame TV)</option>
                {cropPresets.map(opt => (
                  <option key={opt.id} value={opt.id}>{opt.label}</option>
                ))}
              </select>
            </div>

            <div className="flex gap-2">
              <button
                className={`flex-1 rounded px-4 py-2 text-white ${
                  cropperReady
                    ? 'bg-indigo-600 hover:bg-indigo-700'
                    : 'bg-gray-400 cursor-not-allowed'
                }`}
                onClick={handleCrop}
                disabled={!cropperReady || cropActionLoading}
              >
                {cropActionLoading ? 'Cropping…' : cropperReady ? 'Apply Crop' : 'Loading...'}
              </button>
              <button
                className="flex-1 bg-secondary text-secondary-foreground rounded px-4 py-2 hover:bg-secondary/80"
                onClick={() => {
                  if (cropperRef.current?.cropper) {
                    cropperRef.current.cropper.reset();
                    setCropMessage('');
                  }
                }}
                disabled={!cropperReady}
              >
                Reset
              </button>
            </div>

            {cropMessage && (
              <div className={`text-sm ${cropMessage.includes('successfully') ? 'text-green-600' : 'text-red-600'}`}>
                {cropMessage}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CropImageModal;
