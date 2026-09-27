/**
 * CarConfigurator — production configurator experience.
 *
 * Backend owns options, compatibility, validation and pricing. The page only
 * presents backend data and forwards user intent to the canonical API.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Check, RotateCw, Save, Share2, Sparkles } from 'lucide-react';

import ConfiguratorViewer from '../components/configurator/ConfiguratorViewer';
import PricingLocationPicker from '../components/configurator/PricingLocationPicker';
import { useConfiguratorStore } from '../state/configuratorStore';
import { configuratorApi } from '../services/configuratorApi';
import { formatINR } from '../lib/api';
import { buildPurchasablePayload, getValidationMessages, isInteractionSupported, getCameraPresets } from './configuratorPresentation';

function getErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (detail && typeof detail.message === 'string' && detail.message.trim()) return detail.message;
  if (detail && Array.isArray(detail.errors) && detail.errors.length > 0) return detail.errors.filter((item) => typeof item === 'string').join(' · ');
  return error?.message || fallback;
}

function getOptionId(option) { return option?.option_id || option?.color_id || option?.wheel_id || option?.interior_id; }
function getOptionLabel(option) { return option?.display_name || option?.name || option?.color_name || option?.wheel_name || option?.interior_name || getOptionId(option); }
function getOptionPriceDelta(option) { const value = Number(option?.price_delta || option?.additional_price || 0); return Number.isFinite(value) ? value : 0; }

export default function CarConfigurator() {
  const { variantId } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [variant, setVariant] = useState(null);
  const [options, setOptions] = useState(null);
  const [saveState, setSaveState] = useState({ loading: false, error: null, configId: null, shareToken: null });
  const [shareCopied, setShareCopied] = useState(false);
  const requestSequence = useRef(0);
  const store = useConfiguratorStore();

  useEffect(() => {
    if (!variantId) return undefined;
    let cancelled = false;
    async function load() {
      setLoading(true); setError(null); setOptions(null); store.reset();
      try {
        const availRes = await configuratorApi.getAvailability(variantId);
        const { configurator_status: configuratorStatus, asset_id: assetId } = availRes.data;
        const variantData = (await configuratorApi.getVariant(variantId)).data;
        if (cancelled) return;
        setVariant(variantData); store.setVariant(variantId);
        if (configuratorStatus === 'AVAILABLE' && assetId) {
          const assetRes = await configuratorApi.getAsset(variantId);
          if (!cancelled && assetRes.data.available) store.setAsset(assetRes.data.asset);
          else store.setAssetUnavailable(configuratorStatus);
        } else store.setAssetUnavailable(configuratorStatus);
        const optsRes = await configuratorApi.getOptions(variantId);
        if (!cancelled) setOptions(optsRes.data);

        const configToken = new URLSearchParams(window.location.search).get('config');
        if (configToken) {
          const saved = await configuratorApi.loadConfiguration(configToken);
          const savedPurchasable = saved.data?.configuration?.purchasable;
          if (savedPurchasable?.variant_id === variantId && !cancelled) {
            const current = useConfiguratorStore.getState();
            current.setPaint(savedPurchasable.paint_id || null);
            current.setWheels(savedPurchasable.wheel_id || null);
            current.setInterior(savedPurchasable.interior_id || null);
            current.setRoof(savedPurchasable.roof_id || null);
            (savedPurchasable.accessory_ids || []).forEach((id) => current.toggleAccessory(id));
            if (saved.data.city) current.setCity(saved.data.city);
          }
        }
      } catch (err) { if (!cancelled) setError(getErrorMessage(err, 'Failed to load vehicle')); }
      finally { if (!cancelled) setLoading(false); }
    }
    load();
    return () => { cancelled = true; };
  }, [variantId]);

  const validateAndPrice = useCallback(async () => {
    const sequence = ++requestSequence.current;
    const current = useConfiguratorStore.getState();
    if (!current.purchasable.variantId) return;
    const configuration = buildPurchasablePayload(current.purchasable);
    current.setValidationLoading(); current.setPriceLoading();
    try {
      const validationResponse = await configuratorApi.validateConfiguration(configuration);
      if (sequence !== requestSequence.current) return;
      current.setValidationResult(validationResponse.data);
      const messages = getValidationMessages(validationResponse.data);
      if (messages.errors.length || !validationResponse.data.valid) {
        current.setPriceError('Resolve configuration compatibility issues to calculate price');
        return;
      }
      const priceResponse = await configuratorApi.calculatePrice(configuration, current.city);
      if (sequence !== requestSequence.current) return;
      current.setPriceResult(priceResponse.data);
    } catch (err) {
      if (sequence !== requestSequence.current) return;
      const message = getErrorMessage(err, 'Configuration validation failed');
      current.setValidationError(message); current.setPriceError(message);
    }
  }, []);

  useEffect(() => {
    if (store.isInitialized) validateAndPrice();
  }, [store.isInitialized, store.city, store.purchasable.paintId, store.purchasable.wheelId, store.purchasable.interiorId, store.purchasable.roofId, store.purchasable.accessoryIds.join(','), validateAndPrice]);

  const saveConfiguration = async () => {
    const current = useConfiguratorStore.getState();
    if (!current.validation.result?.valid || current.validation.loading) return;
    setSaveState({ loading: true, error: null, configId: null, shareToken: null });
    try {
      const payload = {
        configuration: {
          purchasable: buildPurchasablePayload(current.purchasable),
          interaction: {
            doors: { front_left: current.interaction.doors.frontLeft, front_right: current.interaction.doors.frontRight, rear_left: current.interaction.doors.rearLeft, rear_right: current.interaction.doors.rearRight },
            hood_open: current.interaction.hoodOpen, boot_open: current.interaction.bootOpen, frunk_open: current.interaction.frunkOpen, sunroof_open: current.interaction.sunroofOpen,
            lighting: current.interaction.lighting, camera_preset: current.interaction.cameraPreset,
          },
        },
        city: current.city,
        price_snapshot: current.price.data?.estimated_on_road || null,
        asset_id: current.asset?.asset_id || null,
        asset_version: current.asset?.version || null,
        asset_revision_id: current.asset?.revisionId || null,
      };
      const response = await configuratorApi.saveConfiguration(payload);
      setSaveState({ loading: false, error: null, configId: response.data.config_id, shareToken: response.data.share_token });
    } catch (err) { setSaveState({ loading: false, error: getErrorMessage(err, 'Sign in to save this configuration'), configId: null, shareToken: null }); }
  };

  const copyShareLink = async () => {
    if (!saveState.shareToken) return;
    const url = `${window.location.origin}${window.location.pathname}?config=${encodeURIComponent(saveState.shareToken)}`;
    try { await navigator.clipboard.writeText(url); setShareCopied(true); window.setTimeout(() => setShareCopied(false), 1800); }
    catch { setSaveState((state) => ({ ...state, error: 'Unable to copy share link' })); }
  };

  if (loading) return <main className="min-h-screen bg-[#050505] pt-24 text-white"><div className="mx-auto max-w-7xl px-6 py-20 text-center text-xs uppercase tracking-widest text-white/40">Loading configurator…</div></main>;
  if (error) return <main className="min-h-screen bg-[#050505] pt-24 text-white"><div className="mx-auto max-w-lg px-6 py-20 text-center"><p className="text-red-400 text-sm">{error}</p><Link to="/cars" className="mt-6 inline-flex items-center gap-2 text-xs uppercase tracking-widest text-white/40 hover:text-white"><ArrowLeft size={14} /> Back to cars</Link></div></main>;

  const price = store.price.data;
  const validation = store.validation.result;
  const canCommit = Boolean(validation?.valid) && !store.validation.loading && !store.price.loading;
  return <main className="min-h-screen bg-[#050505] pt-20 text-white"><div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6 lg:px-10">
    <div className="mb-5 flex flex-wrap items-center justify-between gap-4"><Link to="/cars" className="inline-flex items-center gap-2 text-xs uppercase tracking-widest text-white/40 hover:text-white"><ArrowLeft size={14} /> Exit configurator</Link><div className="inline-flex items-center gap-2 rounded-full border border-amber-400/20 bg-amber-400/5 px-4 py-2 text-[10px] uppercase tracking-widest text-amber-300"><Sparkles size={12} /> {store.asset.available ? 'Live 3D configurator' : '3D Coming Soon'}</div></div>
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]"><div className="overflow-hidden rounded-[24px] border border-white/10 bg-[#0a0a0a]"><div className="relative p-2"><ConfiguratorViewer options={options} /></div></div>
    <aside className="space-y-4"><div className="rounded-2xl border border-white/10 bg-[#0d0d0d] p-5"><div className="text-[10px] uppercase tracking-widest text-amber-400">{variant?.brand || ''}</div><h1 className="mt-1 text-2xl font-light">{variant?.model || variantId}</h1>{variant?.variant && <p className="mt-0.5 text-xs text-white/40">{variant.variant}</p>}<div className="mt-3 flex items-end justify-between"><div className="font-mono text-3xl text-amber-400">{price ? formatINR(price.estimated_on_road) : '—'}</div>{store.price.loading && <span className="text-[9px] uppercase tracking-widest text-white/30">Updating</span>}</div>{price && <p className="mt-1 text-[10px] text-white/25">{price.price_is_estimate ? 'Estimated on-road' : 'Configured price'} · {price.city || store.city || 'base pricing'}</p>}{store.price.error && <p className="mt-2 text-[10px] text-red-400">{store.price.error}</p>}</div>
      <OptionPanel title="Exterior colour" options={options?.colors} selectedId={store.purchasable.paintId} onSelect={store.setPaint} colorMode />
      <OptionPanel title="Wheels" options={options?.wheels} selectedId={store.purchasable.wheelId} onSelect={store.setWheels} />
      <OptionPanel title="Interior" options={options?.interiors} selectedId={store.purchasable.interiorId} onSelect={store.setInterior} />
      <OptionPanel title="Roof" options={options?.roofs} selectedId={store.purchasable.roofId} onSelect={store.setRoof} />
      <OptionPanel title="Accessories" options={options?.accessories} selectedIds={store.purchasable.accessoryIds} onToggle={store.toggleAccessory} multi />
      <ValidationPanel validation={validation} error={store.validation.error} />
      <PriceBreakdown price={price} />
      <ConfigurationSummary variant={variant} options={options} purchasable={store.purchasable} />
      <PricingLocationPicker variantId={variantId} city={store.city} setCity={store.setCity} />
      <SaveSharePanel canCommit={canCommit} saveState={saveState} onSave={saveConfiguration} onShare={copyShareLink} shareCopied={shareCopied} />
      {saveState.shareToken && <Link to={`/configurator/conversion?config=${encodeURIComponent(saveState.shareToken)}`} className="block w-full rounded-xl border border-amber-400/30 bg-amber-400/5 py-3 text-center text-xs font-bold uppercase tracking-widest text-amber-300 transition hover:bg-amber-400/10">Finance · Insurance · Dealer →</Link>}
      <InteractionPanel supportedInteractions={store.asset.supportedInteractions} /><CameraPanel supportedInteractions={store.asset.supportedInteractions} />
      <Link aria-disabled={!canCommit} className={`block w-full rounded-xl py-3 text-center text-xs font-bold uppercase tracking-widest transition ${canCommit ? 'bg-amber-400 text-black hover:bg-amber-300' : 'pointer-events-none bg-white/10 text-white/20'}`} to={canCommit ? `/book/${variantId}` : '#'}>Book configured test drive →</Link>
    </aside></div></div></main>;
}

function OptionPanel({ title, options = [], selectedId, selectedIds = [], onSelect, onToggle, multi = false, colorMode = false }) {
  if (!options.length) return null;
  return <div className="rounded-2xl border border-white/10 bg-[#0d0d0d] p-5"><div className="mb-3 flex items-center justify-between"><h3 className="text-[10px] uppercase tracking-widest text-white/40">{title}</h3>{multi && <span className="text-[9px] text-white/20">Multiple</span>}</div><div className="grid grid-cols-2 gap-2">{options.map((option) => { const id = getOptionId(option); const selected = multi ? selectedIds.includes(id) : selectedId === id; const disabled = option.available === false; const delta = getOptionPriceDelta(option); return <button key={id} type="button" disabled={disabled} onClick={() => (multi ? onToggle(id) : onSelect(id))} aria-pressed={selected} className={`rounded-xl border p-2 text-left transition ${selected ? 'border-amber-400 bg-amber-400/10' : 'border-white/10 hover:border-white/30'} ${disabled ? 'cursor-not-allowed opacity-30' : ''}`}>{colorMode && (option.primary_hex || option.preview_color_hex) ? <span className="mb-2 block h-8 rounded-lg border border-white/20" style={{ backgroundColor: option.primary_hex || option.preview_color_hex }} /> : option.preview_image_url ? <img src={option.preview_image_url} alt="" className="mb-2 h-16 w-full rounded-lg object-cover" loading="lazy" /> : null}<span className="flex items-center justify-between gap-2"><span className="truncate text-[10px] text-white/70">{getOptionLabel(option)}</span>{selected && <Check size={12} className="shrink-0 text-amber-300" />}</span>{delta > 0 && <span className="mt-1 block font-mono text-[9px] text-amber-300">+{formatINR(delta)}</span>}</button>; })}</div></div>;
}

function ValidationPanel({ validation, error }) { if (!validation && !error) return null; const messages = getValidationMessages(validation); const errors = error ? [error] : messages.errors; return <div className="rounded-2xl border border-white/10 bg-[#0d0d0d] p-5"><h3 className="mb-3 text-[10px] uppercase tracking-widest text-white/40">Compatibility</h3>{validation?.valid && !errors.length && <p className="text-xs text-emerald-300">Configuration validated by Auto AI India.</p>}{errors.map((message) => <p key={message} className="mb-1 text-[10px] text-red-400">{message}</p>)}{messages.warnings.map((message) => <p key={message} className="mb-1 text-[10px] text-amber-300">{message}</p>)}</div>; }

function PriceBreakdown({ price }) { if (!price) return null; const rows = [['Base ex-showroom', price.base_ex_showroom], ...(price.option_deltas || []).map((item) => [item.name, item.amount]), price.rto != null ? ['RTO', price.rto] : null, price.insurance_approx != null ? ['Insurance approx.', price.insurance_approx] : null, price.tcs != null ? ['TCS', price.tcs] : null, price.other_charges != null ? ['Other charges', price.other_charges] : null].filter(Boolean); return <div className="rounded-2xl border border-white/10 bg-[#0d0d0d] p-5"><div className="mb-3 flex items-center justify-between"><h3 className="text-[10px] uppercase tracking-widest text-white/40">Price breakdown</h3><span className="text-[9px] text-white/20">Backend</span></div><div className="space-y-2">{rows.map(([label, amount]) => <div key={label} className="flex justify-between gap-4 text-[10px]"><span className="text-white/40">{label}</span><span className="font-mono text-white/70">{formatINR(amount)}</span></div>)}{price.total_discount > 0 && <div className="flex justify-between border-t border-white/5 pt-2 text-[10px]"><span className="text-emerald-300/70">Offers/discount</span><span className="font-mono text-emerald-300">−{formatINR(price.total_discount)}</span></div>}</div><div className="mt-4 flex justify-between border-t border-white/10 pt-3"><span className="text-[10px] uppercase tracking-widest text-white/40">Estimated on-road</span><span className="font-mono text-lg text-amber-400">{formatINR(price.estimated_on_road)}</span></div>{price.source && <p className="mt-2 text-[9px] text-white/20">Source: {price.source} · Effective {price.effective_date}</p>}</div>; }

function ConfigurationSummary({ variant, options, purchasable }) { const find = (collection, id) => collection?.find((item) => getOptionId(item) === id); const values = [['Vehicle', [variant?.brand, variant?.model, variant?.variant].filter(Boolean).join(' ')], ['Colour', getOptionLabel(find(options?.colors, purchasable.paintId))], ['Wheels', getOptionLabel(find(options?.wheels, purchasable.wheelId))], ['Interior', getOptionLabel(find(options?.interiors, purchasable.interiorId))], ['Roof', getOptionLabel(find(options?.roofs, purchasable.roofId))], ['Accessories', (purchasable.accessoryIds || []).map((id) => getOptionLabel(find(options?.accessories, id))).filter(Boolean).join(', ') || 'None']]; return <div className="rounded-2xl border border-white/10 bg-[#0d0d0d] p-5"><h3 className="mb-3 text-[10px] uppercase tracking-widest text-white/40">Your configuration</h3><div className="space-y-2">{values.map(([label, value]) => <div key={label} className="flex gap-3 text-[10px]"><span className="w-20 shrink-0 text-white/25">{label}</span><span className="text-white/65">{value || 'Not selected'}</span></div>)}</div></div>; }

function SaveSharePanel({ canCommit, saveState, onSave, onShare, shareCopied }) { return <div className="rounded-2xl border border-white/10 bg-[#0d0d0d] p-5"><h3 className="mb-3 text-[10px] uppercase tracking-widest text-white/40">Save & share</h3><div className="grid grid-cols-2 gap-2"><button type="button" disabled={!canCommit || saveState.loading} onClick={onSave} className="flex items-center justify-center gap-2 rounded-xl border border-white/10 py-2 text-[10px] uppercase tracking-wider text-white/60 hover:border-white/30 disabled:opacity-25"><Save size={12} /> {saveState.loading ? 'Saving' : 'Save'}</button><button type="button" disabled={!saveState.shareToken} onClick={onShare} className="flex items-center justify-center gap-2 rounded-xl border border-white/10 py-2 text-[10px] uppercase tracking-wider text-white/60 hover:border-white/30 disabled:opacity-25">{shareCopied ? <Check size={12} /> : <Share2 size={12} />} {shareCopied ? 'Copied' : 'Share'}</button></div>{saveState.configId && <p className="mt-2 flex items-center gap-1 text-[9px] text-emerald-300"><Check size={10} /> Saved configuration {saveState.configId.slice(0, 8)}</p>}{saveState.error && <p className="mt-2 text-[9px] text-red-400">{saveState.error}</p>}</div>; }

function InteractionPanel({ supportedInteractions = [] }) { const store = useConfiguratorStore(); const controls = [['Hood', 'Hood_Open', store.interaction.hoodOpen, store.toggleHood], ['Boot', 'Boot_Open', store.interaction.bootOpen, store.toggleBoot], ['Sunroof', 'Sunroof_Open', store.interaction.sunroofOpen, store.toggleSunroof], ['Headlights', 'Headlights', store.interaction.lighting.headlights, () => store.toggleLight('headlights')], ['DRL', 'DRL', store.interaction.lighting.drl, () => store.toggleLight('drl')], ['Hazard', 'Hazard', store.interaction.lighting.hazard, store.toggleHazard], ['Door FL', 'Door_FL_Open', store.interaction.doors.frontLeft, () => store.toggleDoor('frontLeft')], ['Door FR', 'Door_FR_Open', store.interaction.doors.frontRight, () => store.toggleDoor('frontRight')], ['Door RL', 'Door_RL_Open', store.interaction.doors.rearLeft, () => store.toggleDoor('rearLeft')], ['Door RR', 'Door_RR_Open', store.interaction.doors.rearRight, () => store.toggleDoor('rearRight')]]; return <div className="rounded-2xl border border-white/10 bg-[#0d0d0d] p-5"><h3 className="mb-3 text-[10px] uppercase tracking-widest text-white/40">3D interactions</h3><div className="grid grid-cols-3 gap-2">{controls.map(([label, capability, active, action]) => { const supported = isInteractionSupported(supportedInteractions, capability); return <button key={label} type="button" disabled={!supported} onClick={action} title={supported ? label : 'Not supported by this verified asset'} aria-pressed={active} className={`rounded-lg border py-2 text-[9px] uppercase tracking-wider transition ${active ? 'border-amber-400 bg-amber-400/10 text-amber-300' : 'border-white/10 text-white/40 hover:border-white/30'} ${!supported ? 'cursor-not-allowed opacity-20' : ''}`}>{label}</button>; })}</div><p className="mt-3 text-[9px] text-white/20">Only interactions declared by the verified 3D asset are enabled.</p></div>; }

function CameraPanel({ supportedInteractions = [] }) { const setCameraPreset = useConfiguratorStore((state) => state.setCameraPreset); const cameraPreset = useConfiguratorStore((state) => state.interaction.cameraPreset); const setAutoRotate = useConfiguratorStore((state) => state.setAutoRotate); const autoRotate = useConfiguratorStore((state) => state.interaction.autoRotate); const presets = getCameraPresets(supportedInteractions); return <div className="rounded-2xl border border-white/10 bg-[#0d0d0d] p-5"><div className="mb-3 flex items-center justify-between"><h3 className="text-[10px] uppercase tracking-widest text-white/40">Camera</h3><button type="button" disabled={!presets.length} onClick={() => setAutoRotate(!autoRotate)} aria-pressed={autoRotate} className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-[9px] uppercase tracking-wider transition ${autoRotate ? 'border-amber-400 text-amber-300' : 'border-white/10 text-white/30'} disabled:cursor-not-allowed disabled:opacity-20`}><RotateCw size={10} /> Auto</button></div>{presets.length ? <div className="flex flex-wrap gap-1.5">{presets.map((preset) => <button type="button" key={preset} onClick={() => setCameraPreset(preset)} className={`rounded-lg border px-2.5 py-1 text-[9px] uppercase tracking-wider transition ${cameraPreset === preset ? 'border-amber-400 text-amber-300' : 'border-white/10 text-white/30 hover:border-white/30'}`}>{preset}</button>)}</div> : <p className="text-[9px] text-white/25">No verified camera capabilities are available for this asset.</p>}</div>; }
