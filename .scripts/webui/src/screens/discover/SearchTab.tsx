import { useEffect, useRef, useState } from 'react';
import type { CreateSearchResponse, DiscoverySession } from '../../api/types';
import { discoverSearchHref } from '../../hooks/useHashRoute';
import { primedSession, useRelatedCreated } from '../../hooks/useRelatedLookup';
import { SearchForm } from './SearchForm';
import { SearchHistory } from './SearchHistory';
import { SearchResult } from './SearchResult';
import { isActiveSearch, useSearchList } from './useDiscovery';

interface SearchTabProps {
  /** Session shown (`#/discover/searches/{id}`); null shows the form. */
  id: string | null;
  /** `?q=` from an entry link; prefills the form. */
  prefill: string | null;
  reloadToken: number;
}

/** `#/discover[/searches/{id}]`: the form or one session beside the search history. */
export function SearchTab({ id, prefill, reloadToken }: SearchTabProps) {
  const list = useSearchList(reloadToken);
  const mainRef = useRef<HTMLElement>(null);
  const previousId = useRef(id);
  /** The session POST just returned, so its result opens without waiting for the first GET. */
  const [created, setCreated] = useState<DiscoverySession | null>(null);
  const active = list.data?.searches.find((search) => isActiveSearch(search.status)) ?? null;
  const { reload } = list;
  // A 인용·피인용 list created from a card here adds a history row.
  useRelatedCreated(reload);

  // Opening another session (or going back to the form) moves focus to it so the change is announced.
  // A 인용·피인용 list opened from the 일일 후보 tab mounts this tab with the card's focus gone: it lands
  // here too (a new screen's own heading focus, from App, comes after and wins).
  useEffect(() => {
    if (previousId.current === id) {
      const lost = document.activeElement === null || document.activeElement === document.body;
      if (id !== null && lost && primedSession(id)) mainRef.current?.focus();
      return;
    }
    previousId.current = id;
    mainRef.current?.focus();
  }, [id]);

  const onCreated = (response: CreateSearchResponse) => {
    setCreated(response.search);
    reload();
    window.location.hash = discoverSearchHref(response.search.search_id);
  };

  // The session a POST just returned (this form, or 인용·피인용 from any screen) opens without waiting for its GET.
  const initial = id === null ? null : created?.search_id === id ? created : primedSession(id);

  return (
    <div className="discover-search">
      {id ? (
        <SearchResult
          key={id}
          searchId={id}
          reloadToken={reloadToken}
          initial={initial}
          sectionRef={mainRef}
          onChanged={reload}
        />
      ) : (
        <SearchForm
          prefill={prefill}
          active={active}
          reloadToken={reloadToken}
          sectionRef={mainRef}
          onCreated={onCreated}
          onStale={reload}
        />
      )}
      <SearchHistory list={list} currentId={id} />
    </div>
  );
}
