import { SiteHeader } from '@/components/site-header'
import { SectionCards } from '@/components/section-cards'
import { BpmDistributionChart } from '@/components/charts/bpm-distribution'
import { MoodDistributionChart } from '@/components/charts/mood-distribution'
import { CamelotWheelChart } from '@/components/charts/camelot-wheel'
import { LufsRangeChart } from '@/components/charts/lufs-range'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
      <div className="flex flex-1 flex-col gap-6 p-4">
        <SectionCards stats={stats} />

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">BPM Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <BpmDistributionChart data={bpmData} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">LUFS Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <LufsRangeChart data={lufsData} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Mood Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <MoodDistributionChart data={moodData} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Key Distribution (Camelot)</CardTitle>
            </CardHeader>
            <CardContent>
              <CamelotWheelChart data={keyData} />
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Analysis Coverage</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {coverageData.length === 0 ? (
              <p className="text-sm text-muted-foreground">No analysis data yet.</p>
            ) : (
              coverageData.map((item) => {
                const pct = totalCoverage > 0 ? Math.round((item.count / totalCoverage) * 100) : 0
                const label = ANALYSIS_LEVELS[item.level] ?? `Level ${item.level}`
                return (
                  <div key={item.level} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span>{label}</span>
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
