'use client';

/** Minimal i18n layer — user-visible strings live here, never hardcoded in JSX
 * (CLAUDE.md note: the Terminal will likely be Korean-localized). */
import { useCanvas } from './store';

const STRINGS = {
  en: {
    companies: 'companies',
    depth: 'Depth',
    supplyChain: 'Supply chain',
    revenueFlow: 'Revenue flow',
    investment: 'Investment',
    cost: 'Cost',
    rnd: 'R&D',
    predict: 'Predict',
    divisions: 'Divisions',
    products: 'Products',
    keyCustomers: 'Key customers',
    revenue: 'Revenue',
    margin: 'Margin',
    marketCap: 'Market cap',
    baseDate: 'Base date',
    nextUpdate: 'Next update',
    priceDelayed: 'Price (delayed feed)',
    showFlow: 'Trace flow →',
    notAdvice:
      'Not investment advice. Figures carry an as-of date & source. Predict is a momentum simulation, not a forecast.',
    noThemes: 'No published themes yet. Publish one in Studio.',
    loading: 'Loading value chain…',
  },
  ko: {
    companies: '개 기업',
    depth: '깊이',
    supplyChain: '공급망',
    revenueFlow: '매출 흐름',
    investment: '투자',
    cost: '원가',
    rnd: '연구개발',
    predict: '예측',
    divisions: '사업부',
    products: '제품',
    keyCustomers: '주요 고객',
    revenue: '매출',
    margin: '마진',
    marketCap: '시가총액',
    baseDate: '기준일',
    nextUpdate: '다음 업데이트',
    priceDelayed: '주가 (지연 시세)',
    showFlow: '흐름 추적 →',
    notAdvice:
      '투자 자문이 아닙니다. 모든 수치에는 기준일과 출처가 있습니다. 예측은 모멘텀 시뮬레이션이며 확정 전망이 아닙니다.',
    noThemes: '게시된 테마가 없습니다. Studio에서 게시하세요.',
    loading: '밸류체인 불러오는 중…',
  },
} as const;

export type StringKey = keyof (typeof STRINGS)['en'];

export function useT(): (k: StringKey) => string {
  const lang = useCanvas((s) => s.lang);
  return (k) => STRINGS[lang][k] ?? STRINGS.en[k];
}
