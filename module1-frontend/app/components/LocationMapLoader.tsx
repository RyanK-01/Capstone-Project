
'use client';

import dynamic from 'next/dynamic';

const LocationMap = dynamic(
  () => import('@/app/components/LocationMap'),
  {
    ssr: false,
    loading: () => (
      <div className="h-[400px] animate-pulse rounded-lg bg-gray-100" />
    ),
  },
);

export default LocationMap;
