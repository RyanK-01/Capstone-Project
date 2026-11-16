
'use client';

import { useEffect, useState } from 'react';
import { useAuth, apiFetch } from './AuthContext';
import {
    MapContainer,
    TileLayer,
    Circle,
    CircleMarker,
    Popup,
    useMap,
} from 'react-leaflet';
import type { LatLngExpression } from 'leaflet';

type LocationMapProps = {
    latitude: number;
    longitude: number;
    radiusMeters: number;
};

type Coordinates = {
    latitude: number;
    longitude: number;
};

function MapUpdater({
    latitude,
    longitude,
}: {
    latitude: number;
    longitude: number;
}) {
    const map = useMap();

    useEffect(() => {
        map.setView([latitude, longitude], map.getZoom());
    }, [map, latitude, longitude]);

    return null;
}

export default function LocationMap({
    latitude,
    longitude,
    radiusMeters,
}: LocationMapProps) {
    const [userLocation, setUserLocation] =
        useState<Coordinates | null>(null);
    const [geoError, setGeoError] = useState('');

    const { isAuthenticated } = useAuth();

    const center: LatLngExpression = [latitude, longitude];

    function locateUser() {

        if (!navigator.geolocation) {
            setGeoError('Geolocation is not supported by this browser.');
            return;
        }
        const fetchData = async () => {
            const response = await apiFetch(
                `${process.env.NEXT_PUBLIC_API_BASE_URL}/users/me`,
                { method: 'GET' }
            );

            try {
                const { geolocation_consent } = await response.json();

                if (geolocation_consent === false) {
                    setGeoError('Please consent to geolocation use in the profile page.');
                    return;
                }
            } catch {

            }
        }

        useEffect(() => {
            if (!isAuthenticated()) {
                setGeoError('You need to be logged in for geolocation services.');
                return;
            }
            fetchData();
        }, [isAuthenticated])


        setGeoError('');

        navigator.geolocation.getCurrentPosition(
            (position) => {
                setUserLocation({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                });
            },
            (error) => {
                setGeoError(
                    error.code === error.PERMISSION_DENIED
                        ? 'Location permission was denied.'
                        : 'Unable to retrieve your location.',
                );
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
            },
        );
    }

    if (
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude) ||
        latitude < -90 ||
        latitude > 90 ||
        longitude < -180 ||
        longitude > 180 ||
        !Number.isFinite(radiusMeters) ||
        radiusMeters < 0
    ) {
        return <p>Invalid map coordinates or radius.</p>;
    }

    return (
        <div className="space-y-3">
            <div className="h-[400px] overflow-hidden rounded-lg border">
                <MapContainer
                    center={center}
                    zoom={16}
                    scrollWheelZoom
                    className="h-full w-full"
                >
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
                        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />

                    <MapUpdater
                        latitude={latitude}
                        longitude={longitude}
                    />

                    <Circle
                        center={center}
                        radius={radiusMeters}
                        pathOptions={{
                            color: 'blue',
                            fillColor: 'blue',
                            fillOpacity: 0.15,
                        }}
                    />

                    <CircleMarker
                        center={center}
                        radius={7}
                        pathOptions={{
                            color: 'white',
                            weight: 2,
                            fillColor: 'blue',
                            fillOpacity: 1,
                        }}
                    >
                        <Popup>
                            <div>
                                <strong>Target location</strong>
                                <br />
                                Latitude: {latitude}
                                <br />
                                Longitude: {longitude}
                                <br />
                                Radius: {radiusMeters} m
                            </div>
                        </Popup>
                    </CircleMarker>

                    {userLocation && (
                        <CircleMarker
                            center={[
                                userLocation.latitude,
                                userLocation.longitude,
                            ]}
                            radius={7}
                            pathOptions={{
                                color: 'white',
                                weight: 2,
                                fillColor: 'green',
                                fillOpacity: 1,
                            }}
                        >
                            <Popup>Your current location</Popup>
                        </CircleMarker>
                    )}
                </MapContainer>
            </div>


            <button
                type="button"
                onClick={locateUser}
                className="rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700">
                Show my current location
            </button>

            {geoError && (
                <p role="alert" className="text-sm text-red-600">
                    {geoError}
                </p>
            )}
        </div>
    );
}
