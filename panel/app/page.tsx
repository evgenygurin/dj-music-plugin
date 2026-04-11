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
        title="Command Center"
        description="Analysis coverage, curation signals, and mix-readiness."
        badge={
          <Badge variant="secondary" className="dj-data text-[10px]">
            {coveragePct}% analyzed
          </Badge>
        }
        actions={
          <>
            <Link href="/discover" className={buttonVariants({ variant: 'outline', className: 'rounded-xl border-border/30' })}>
              Discover
            </Link>
            <Link href="/library" className={buttonVariants({ className: 'rounded-xl' })}>
              Library
            </Link>
          </>
        }
      />

      <SectionCards stats={stats} />

      {/* BPM — full width */}
      <Card className="shadow-none border-border/20 bg-card/50">
        <CardHeader className="pb-2">
          <CardTitle className="display-heading text-lg">BPM Distribution</CardTitle>
          <CardDescription className="text-xs text-muted-foreground/60">Tempo spread across the library</CardDescription>
        </CardHeader>
        <CardContent>
          <BpmDistributionChart data={bpmData} />
        </CardContent>
      </Card>

      {/* Mood + Camelot */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="shadow-none border-border/20 bg-card/50">
          <CardHeader className="pb-2">
            <CardTitle className="display-heading text-lg">Mood</CardTitle>
            <CardDescription className="text-xs text-muted-foreground/60">Subgenre classification</CardDescription>
          </CardHeader>
          <CardContent>
            <MoodDistributionChart data={moodData} />
          </CardContent>
        </Card>

        <Card className="shadow-none border-border/20 bg-card/50">
          <CardHeader className="pb-2">
            <CardTitle className="display-heading text-lg">Camelot</CardTitle>
            <CardDescription className="text-xs text-muted-foreground/60">Harmonic mixing wheel</CardDescription>
          </CardHeader>
          <CardContent>
            <CamelotWheelChart data={keyData} />
          </CardContent>
        </Card>
      </div>

      {/* LUFS + Coverage */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="shadow-none border-border/20 bg-card/50">
          <CardHeader className="pb-2">
            <CardTitle className="display-heading text-lg">Loudness</CardTitle>
            <CardDescription className="text-xs text-muted-foreground/60">LUFS distribution</CardDescription>
          </CardHeader>
          <CardContent>
            <LufsRangeChart data={lufsData} />
          </CardContent>
        </Card>

        <Card className="shadow-none border-border/20 bg-card/50">
          <CardHeader className="pb-2">
            <CardTitle className="display-heading text-lg">Analysis</CardTitle>
            <CardDescription className="text-xs text-muted-foreground/60">
              {totalAnalyzed > 0
                ? `${totalAnalyzed.toLocaleString()} tracks with features`
                : 'No tracks analyzed yet'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {coverageData.length === 0 ? (
              <p className="text-sm text-muted-foreground/60">
                Run <code className="rounded bg-muted/30 px-1.5 py-0.5 dj-data text-[11px]">classify_mood</code> to start.
              </p>
            ) : (
              coverageData.map((item) => {
                const pct =
                  totalAnalyzed > 0 ? Math.round((item.count / totalAnalyzed) * 100) : 0
                const label = ANALYSIS_LEVELS[item.level] ?? `Level ${item.level}`
                return (
                  <div key={item.level} className="space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground/70">{label}</span>
                      <span className="dj-data text-muted-foreground/50">
                        {item.count.toLocaleString()} ({pct}%)
                      </span>
                    </div>
                    <Progress value={pct} className="h-1" />
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>
      </div>

      {/* Danceability + HP Ratio + Phrase */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="shadow-none border-border/20 bg-card/50">
          <CardHeader className="pb-2">
            <CardTitle className="display-heading text-lg">Danceability</CardTitle>
            <CardDescription className="text-xs text-muted-foreground/60">Rhythmic score</CardDescription>
          </CardHeader>
          <CardContent>
            <DanceabilityDistributionChart data={danceabilityData} />
          </CardContent>
        </Card>

        <Card className="shadow-none border-border/20 bg-card/50">
          <CardHeader className="pb-2">
            <CardTitle className="display-heading text-lg">HP Ratio</CardTitle>
            <CardDescription className="text-xs text-muted-foreground/60">Harmonic vs percussive</CardDescription>
          </CardHeader>
          <CardContent>
            <HpRatioDistributionChart data={hpRatioData} />
          </CardContent>
        </Card>

        <Card className="shadow-none border-border/20 bg-card/50">
          <CardHeader className="pb-2">
            <CardTitle className="display-heading text-lg">Phrases</CardTitle>
            <CardDescription className="text-xs text-muted-foreground/60">Dominant phrase length</CardDescription>
          </CardHeader>
          <CardContent>
            <PhraseDistributionChart data={phraseData} />
          </CardContent>
        </Card>
      </div>

      {/* Quality flags */}
      <Card className="shadow-none border-border/20 bg-card/50">
        <CardHeader className="pb-2">
          <CardTitle className="display-heading text-lg">Quality Flags</CardTitle>
          <CardDescription className="text-xs text-muted-foreground/60">Notable audio characteristics</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 sm:grid-cols-3">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground/60 uppercase tracking-wider">Variable Tempo</p>
              <p className="display-heading text-3xl text-foreground">
                {qualityFlags.variable_tempo_count.toLocaleString()}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground/60 uppercase tracking-wider">Atonal</p>
              <p className="display-heading text-3xl text-foreground">
                {qualityFlags.atonality_count.toLocaleString()}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground/60 uppercase tracking-wider">Avg BPM Confidence</p>
              <p className="display-heading text-3xl text-foreground">
                {(qualityFlags.avg_bpm_confidence * 100).toFixed(1)}%
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </PageShell>
  )
}
