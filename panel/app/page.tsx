import { SiteHeader } from '@/components/site-header'
import { SectionCards } from '@/components/section-cards'
import { BpmDistributionChart } from '@/components/charts/bpm-distribution'
import { MoodDistributionChart } from '@/components/charts/mood-distribution'
import { CamelotWheelChart } from '@/components/charts/camelot-wheel'
import { LufsRangeChart } from '@/components/charts/lufs-range'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  getLibraryStats,
  getBpmDistribution,
  getMoodDistribution,
  getKeyDistribution,
  getLufsDistribution,
  getAnalysisCoverage,
} from '@/lib/queries/dashboard'
import { ANALYSIS_LEVELS } from '@/lib/constants'

export const revalidate = 30

export default async function DashboardPage() {
  const [stats, bpmData, moodData, keyData, lufsData, coverageData] = await Promise.all([
    getLibraryStats(),
    getBpmDistribution(),
    getMoodDistribution(),
    getKeyDistribution(),
    getLufsDistribution(),
    getAnalysisCoverage(),
  ])

  const totalCoverage = coverageData.reduce((sum, d) => sum + d.count, 0)

  return (
    <>
      <SiteHeader title="Dashboard" />
      <div className="flex flex-1 flex-col gap-6 p-4 md:p-6">
        <SectionCards stats={stats} />

        <div className="grid gap-4 md:grid-cols-2">
          <Card className="border-border/50">
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold">BPM Distribution</CardTitle>
              <CardDescription>Tempo spread across your library</CardDescription>
            </CardHeader>
            <CardContent>
              <BpmDistributionChart data={bpmData} />
            </CardContent>
          </Card>

          <Card className="border-border/50">
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold">LUFS Distribution</CardTitle>
              <CardDescription>Loudness levels of analyzed tracks</CardDescription>
            </CardHeader>
            <CardContent>
              <LufsRangeChart data={lufsData} />
            </CardContent>
          </Card>

          <Card className="border-border/50">
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold">Mood Distribution</CardTitle>
              <CardDescription>Subgenre classification breakdown</CardDescription>
            </CardHeader>
            <CardContent>
              <MoodDistributionChart data={moodData} />
            </CardContent>
          </Card>

          <Card className="border-border/50">
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold">Camelot Wheel</CardTitle>
              <CardDescription>Key distribution for harmonic mixing</CardDescription>
            </CardHeader>
            <CardContent>
              <CamelotWheelChart data={keyData} />
            </CardContent>
          </Card>
        </div>

        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">Analysis Coverage</CardTitle>
            <CardDescription>
              {totalCoverage > 0
                ? `${totalCoverage} tracks analyzed across ${coverageData.length} levels`
                : 'No tracks analyzed yet'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {coverageData.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Run <code className="rounded bg-muted px-1 py-0.5 text-xs">classify_mood</code> to
                start analyzing your library.
              </p>
            ) : (
              coverageData.map((item) => {
                const pct = totalCoverage > 0 ? Math.round((item.count / totalCoverage) * 100) : 0
                const label = ANALYSIS_LEVELS[item.level] ?? `Level ${item.level}`
                return (
                  <div key={item.level} className="space-y-1.5">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium">{label}</span>
                      <span className="text-muted-foreground">
                        {item.count.toLocaleString()} ({pct}%)
                      </span>
                    </div>
                    <Progress value={pct} className="h-2" />
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
