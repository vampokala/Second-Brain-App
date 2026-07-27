import type { ChatTruthfulness } from '../../lib/streamChat'
import { Badge } from '../ui/badge'

type Props = {
  truthfulness: ChatTruthfulness
}

function scoreVariant(score: number): 'success' | 'warning' | 'destructive' {
  if (score >= 0.85) return 'success'
  if (score >= 0.6) return 'warning'
  return 'destructive'
}

export function TruthfulnessBadge({ truthfulness }: Props) {
  const { score, nli_faithfulness, citation_groundedness, uncited_claims } = truthfulness
  const title = [
    `Score ${score.toFixed(2)}`,
    `NLI faithfulness ${nli_faithfulness.toFixed(2)}`,
    `Citation groundedness ${citation_groundedness.toFixed(2)}`,
    `${uncited_claims} uncited claim${uncited_claims === 1 ? '' : 's'}`,
  ].join(' · ')

  return (
    <Badge variant={scoreVariant(score)} title={title}>
      Truthfulness {score.toFixed(2)}
    </Badge>
  )
}
