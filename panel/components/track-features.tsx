import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

interface TrackFeaturesProps {
  features: Record<string, unknown> | null
}

function FeatureRow({ label, value }: { label: string; value: unknown }) {
  let display: string
  if (value === null || value === undefined) {
    display = '—'
  } else if (Array.isArray(value)) {
    display = `[${(value as number[]).slice(0, 4).map((v: number) => v.toFixed(3)).join(', ')}...]`
  } else if (typeof value === 'number') {
    display = value.toFixed(4)
  } else {
    display = String(value)
  }

  return (
    <div className="flex justify-between py-1 text-sm border-b border-border/50 last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono tabular-nums">{display}</span>
    </div>
  )
}

const GROUPS = [
  {
    id: 'tempo',
    label: 'Tempo',
    keys: ['bpm', 'bpm_confidence', 'bpm_stability', 'variable_tempo'],
  },
  {
    id: 'loudness',
    label: 'Loudness',
    keys: [
      'integrated_lufs',
      'short_term_lufs_mean',
      'momentary_max_lufs',
      'rms_dbfs',
      'true_peak_db',
      'crest_factor_db',
      'loudness_range_lu',
    ],
  },
  {
    id: 'energy',
    label: 'Energy',
    keys: [
      'energy_mean',
      'energy_max',
      'energy_std',
      'energy_slope',
      'energy_sub',
      'energy_low',
      'energy_lowmid',
      'energy_mid',
      'energy_highmid',
      'energy_high',
    ],
  },
  {
    id: 'spectral',
    label: 'Spectral',
    keys: [
      'spectral_centroid_hz',
      'spectral_rolloff_85',
      'spectral_rolloff_95',
      'spectral_flatness',
      'spectral_flux_mean',
      'spectral_flux_std',
      'spectral_slope',
      'spectral_contrast_db',
      'hnr_db',
    ],
  },
  {
    id: 'key',
    label: 'Key',
    keys: [
      'key_code',
      'key_confidence',
      'atonality',
      'chroma_entropy',
      'chroma_vector',
    ],
  },
  {
    id: 'rhythm',
    label: 'Rhythm',
    keys: [
      'hp_ratio',
      'onset_rate',
      'pulse_clarity',
      'kick_prominence',
      'mfcc_vector',
    ],
  },
  {
    id: 'p1p2',
    label: 'P1/P2',
    keys: [
      'danceability',
      'dissonance',
      'dynamic_complexity',
      'bpm_histogram_peaks',
      'phrase_count',
      'pitch_salience',
    ],
  },
]

export function TrackFeatures({ features }: TrackFeaturesProps) {
  if (!features) {
    return (
      <div className="text-sm text-muted-foreground py-4 text-center">
        No audio features available.
      </div>
    )
  }

  return (
    <Tabs defaultValue="tempo">
      <TabsList className="flex flex-wrap h-auto gap-1">
        {GROUPS.map((g) => (
          <TabsTrigger key={g.id} value={g.id} className="text-xs">
            {g.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {GROUPS.map((g) => (
        <TabsContent key={g.id} value={g.id} className="mt-2">
          <div className="divide-y divide-border/50">
            {g.keys.map((key) => (
              <FeatureRow key={key} label={key} value={features[key]} />
            ))}
          </div>
        </TabsContent>
      ))}
    </Tabs>
  )
}
