import Link from 'next/link'
import { PageHeader, PageShell } from '@/components/page-shell'
import { SectionCards } from '@/components/section-cards'
import { BpmDistributionChart } from '@/components/charts/bpm-distribution'
import { MoodDistributionChart } from '@/components/charts/mood-distribution'
import { CamelotWheelChart } from '@/components/charts/camelot-wheel'
import { LufsRangeChart } from '@/components/charts/lufs-range'
import { DanceabilityDistributionChart } from '@/components/charts/danceability-distribution'
import { HpRatioDistributionChart } from '@/components/charts/hp-ratio-distribution'
import { PhraseDistributionChart } from '@/components/charts/phrase-distribution'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  getLibraryStats,
  getBpmDistribution,
  getMoodDistribution,
  getKeyDistribution,
  getLufsDistribution,
  getAnalysisCoverage,
  getDanceabilityDistribution,
  getHpRatioDistribution,
  getPhraseDistribution,
  getQualityFlags,
} from '@/lib/queries/dashboard'
import { ANALYSIS_LEVELS } from '@/lib/constants'

export const revalidate = 30

export default async function DashboardPage() {
  const [
    stats,
    bpmData,
    moodData,
    keyData,
    lufsData,
    coverageData,
    danceabilityData,
    hpRatioData,
    phraseData,
    qualityFlags,
  ] = await Promise.all([
    getLibraryStats(),
    getBpmDistribution(),
    getMoodDistribution(),
    getKeyDistribution(),
    getLufsDistribution(),
    getAnalysisCoverage(),
    getDanceabilityDistribution(),
    getHpRatioDistribution(),
    getPhraseDistribution(),
    getQualityFlags(),
  ])

  const totalAnalyzed = stats.totalTracks > 0 ? stats.analyzedTracks : 0
  const coveragePct =
    stats.totalTracks > 0 ? Math.round((stats.analyzedTracks / stats.totalTracks) * 100) : 0

  return (
    <PageShell title="Dashboard">
      <PageHeader
        title="Library Command Center"
        description="Track analysis coverage, curation signals, and mix-readiness in one view."
        badge={<Badge variant="secondary">{coveragePct}% analyzed</Badge>}
        actions={
          <>
            <Link href="/discover" className={buttonVariants({ variant: 'outline' })}>
              Discover Tracks
            </Link>
            <Link href="/library" className={buttonVariants()}>
              Open Library
            </Link>
          </>
        }
      />

      <SectionCards stats={stats} />

      {/* BPM Distribution — full width */}
      <Card className="shadow-none">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">BPM Distribution</CardTitle>
          <CardDescription>Tempo spread across your library</CardDescription>
        </CardHeader>
        <CardContent>
          <BpmDistributionChart data={bpmData} />
        </CardContent>
      </Card>

      {/* Mood + Camelot */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="shadow-none">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Mood Distribution</CardTitle>
            <CardDescription>Subgenre classification breakdown</CardDescription>
          </CardHeader>
          <CardContent>
            <MoodDistributionChart data={moodData} />
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Key Distribution</CardTitle>
            <CardDescription>Camelot wheel — harmonic mixing</CardDescription>
          </CardHeader>
          <CardContent>
            <CamelotWheelChart data={keyData} />
          </CardContent>
        </Card>
      </div>

      {/* LUFS + Coverage */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="shadow-none">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">LUFS Distribution</CardTitle>
            <CardDescription>Loudness levels of analyzed tracks</CardDescription>
          </CardHeader>
          <CardContent>
            <LufsRangeChart data={lufsData} />
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Analysis Coverage</CardTitle>
            <CardDescription>
              {totalAnalyzed > 0
                ? `${totalAnalyzed.toLocaleString()} tracks with audio features`
                : 'No tracks analyzed yet'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {coverageData.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Run{' '}
                <code className="rounded bg-muted px-1 py-0.5 text-xs">classify_mood</code>{' '}
                to start analyzing your library.
              </p>
            ) : (
              coverageData.map((item) => {
                const pct =
                  totalAnalyzed > 0 ? Math.round((item.count / totalAnalyzed) * 100) : 0
                const label = ANALYSIS_LEVELS[item.level] ?? `Level ${item.level}`
                return (
                  <div key={item.level} className="space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">{label}</span>
                      <span className="tabular-nums text-muted-foreground">
                        {item.count.toLocaleString()} ({pct}%)
                      </span>
                    </div>
                    <Progress value={pct} className="h-1.5" />
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>
      </div>

      {/* Danceability + HP Ratio + Phrase */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="shadow-none">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Danceability</CardTitle>
            <CardDescription>Rhythmic danceability score</CardDescription>
          </CardHeader>
          <CardContent>
            <DanceabilityDistributionChart data={danceabilityData} />
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">HP Ratio</CardTitle>
            <CardDescription>Harmonic-to-percussive ratio</CardDescription>
          </CardHeader>
          <CardContent>
            <HpRatioDistributionChart data={hpRatioData} />
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Phrase Length</CardTitle>
            <CardDescription>Dominant phrase length in bars</CardDescription>
          </CardHeader>
          <CardContent>
            <PhraseDistributionChart data={phraseData} />
          </CardContent>
        </Card>
      </div>

      {/* Quality flags */}
      <Card className="shadow-none">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Quality Flags</CardTitle>
          <CardDescription>Tracks with notable audio characteristics</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-0.5">
              <p className="text-sm text-muted-foreground">Variable Tempo</p>
              <p className="text-2xl font-semibold tabular-nums">
                {qualityFlags.variable_tempo_count.toLocaleString()}
              </p>
            </div>
            <div className="space-y-0.5">
              <p className="text-sm text-muted-foreground">Atonal</p>
              <p className="text-2xl font-semibold tabular-nums">
                {qualityFlags.atonality_count.toLocaleString()}
              </p>
            </div>
            <div className="space-y-0.5">
              <p className="text-sm text-muted-foreground">Avg BPM Confidence</p>
              <p className="text-2xl font-semibold tabular-nums">
                {(qualityFlags.avg_bpm_confidence * 100).toFixed(1)}%
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </PageShell>
  )
}
