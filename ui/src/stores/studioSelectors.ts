import { useStore } from './useStore'

export interface StudioNamespace {
  selectedModelPerMode: ReturnType<typeof useStore.getState>['selectedModelPerMode']
  models: ReturnType<typeof useStore.getState>['models']
  params: ReturnType<typeof useStore.getState>['params']
  generationMode: ReturnType<typeof useStore.getState>['generationMode']
  activatedLoras: string[]
  loraWeights: ReturnType<typeof useStore.getState>['loraWeights']
}

type StoreState = ReturnType<typeof useStore.getState>
type StudioField = keyof StudioNamespace

const selectors: { [K in StudioField]: (state: StoreState) => StudioNamespace[K] } = {
  selectedModelPerMode: state => state.selectedModelPerMode,
  models: state => state.models,
  params: state => state.params,
  generationMode: state => state.generationMode,
  activatedLoras: state => state.params.activated_loras || [],
  loraWeights: state => state.loraWeights,
}

export function useStudioSlice<K extends StudioField>(field: K): StudioNamespace[K] {
  return useStore(selectors[field])
}

export function readStudioNamespace(): StudioNamespace {
  const state = useStore.getState()
  return {
    selectedModelPerMode: state.selectedModelPerMode,
    models: state.models,
    params: state.params,
    generationMode: state.generationMode,
    activatedLoras: state.params.activated_loras || [],
    loraWeights: state.loraWeights,
  }
}
