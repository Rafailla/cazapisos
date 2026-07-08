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
};

export type RecipientRow = {
  id: number;
  email: string;
  active: boolean;
};
