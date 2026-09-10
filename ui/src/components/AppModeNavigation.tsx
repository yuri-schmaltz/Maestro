import { useStore } from '../stores/useStore'

export function MaestroBrand({
  compact = false,
  className = '',
}: {
  compact?: boolean
  className?: string
}) {
  const appVersion = useStore(state => state.systemConfig?.app_version)

  return (
    <div className={`flex shrink-0 items-center gap-2 ${className}`}>
      <img
        src="/maestro-home-icon-orange.png"
        alt=""
        className={`${compact ? 'h-7 w-7 rounded-[7px]' : 'h-8 w-8 rounded-lg'} shrink-0`}
      />
      <>
        {!compact && (
          <span className="text-sm font-semibold tracking-tight text-text-primary">Maestro</span>
        )}
        {appVersion && (
          <span className={`${compact ? 'text-[9px]' : 'mt-0.5 text-[10px]'} whitespace-nowrap font-normal text-text-muted`}>v{appVersion}</span>
        )}
      </>
    </div>
  )
}
