export type FilterRow = {
  id: string;
  profile_name: string;
  zona: string | null;
  property_type: string | null;
  price_max: number | null;
  bedrooms_min: number | null;
  bathrooms_min: number | null;
  m2_min: number | null;
  active: boolean;
  requires_elevator: boolean;
  floor_preference: string | null;
  requires_garage: boolean;
};

export type RecipientRow = {
  id: number;
  email: string;
  active: boolean;
};

export type PlatformStatusRow = {
  id: string;
  name: string;
  last_checked_at: string | null;
  last_run_new_count: number | null;
};
