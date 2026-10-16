'use client';

import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect } from 'react';
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet';

export interface Pin {
  lat: number;
  lng: number;
}

/** A CSS pin: Leaflet's default marker images do not survive bundlers, so we draw our own. */
const pinIcon = L.divIcon({
  className: '',
  html: '<div style="width:28px;height:28px;border-radius:50% 50% 50% 0;background:#4B68FF;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.4);transform:rotate(-45deg)"></div>',
  iconSize: [28, 28],
  iconAnchor: [14, 28],
});

function Clicks({ onPick }: { onPick: (p: Pin) => void }) {
  useMapEvents({ click: (e) => onPick({ lat: e.latlng.lat, lng: e.latlng.lng }) });
  return null;
}

function Recenter({ pin }: { pin: Pin | null }) {
  const map = useMap();
  useEffect(() => {
    if (pin) map.setView([pin.lat, pin.lng], Math.max(map.getZoom(), 15), { animate: true });
  }, [map, pin]);
  return null;
}

export default function LocationMap({ pin, onPick, label }: { pin: Pin | null; onPick: (p: Pin) => void; label: string }) {
  const center: [number, number] = pin ? [pin.lat, pin.lng] : [31.5204, 74.3587];
  return (
    <div role="application" aria-label={label} className="h-72 w-full overflow-hidden rounded-2xl border border-border sm:h-96">
      <MapContainer center={center} zoom={pin ? 15 : 12} scrollWheelZoom className="h-full w-full">
        <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Clicks onPick={onPick} />
        <Recenter pin={pin} />
        {pin && (
          <Marker
            position={[pin.lat, pin.lng]}
            icon={pinIcon}
            draggable
            eventHandlers={{ dragend: (e) => onPick({ lat: e.target.getLatLng().lat, lng: e.target.getLatLng().lng }) }}
          />
        )}
      </MapContainer>
    </div>
  );
}
