export const palette = {
  primary: '#4B68FF', primaryStrong: '#3A56F0', secondary: '#FFE24B', accent: '#B0C7FF',
  iconPrimary: '#8D8D8D',
  error: '#D32F2F', success: '#388E3C', warning: '#F57C00', info: '#1976D2',
  black: '#232323', pureBlack: '#000000', darkerGrey: '#4F4F4F', darkGrey: '#939393',
  grey: '#D9D9D9', softGrey: '#F4F4F4', lightGrey: '#F9F9F9', white: '#FFFFFF', transparent: '#00000000',
  textPrimary: '#272727', textSecondary: '#656565', textWhite: '#FFFFFF',
  light: '#F6F6F6', primaryBackground: '#F5F5F5', lightContainer: '#F6F6F6',
  buttonPrimary: '#4B68FF', buttonSecondary: '#6C757D', buttonDisabled: '#C4C4C4', borderPrimary: '#D9D9D9',
  dark: '#272727', textDarkPrimary: '#F6F6F6', textDarkSecondary: '#F6F6F699',
  darkScaffoldBackground: '#0000001A', darkContainer: '#FFFFFF1A', borderSecondary: '#313131',
  darkPage: '#121212',
} as const;

const status = {
  error: palette.error, success: palette.success, warning: palette.warning, info: palette.info,
  errorTint: '#D32F2F1F', successTint: '#388E3C1F', warningTint: '#F57C001F', infoTint: '#1976D21F',
};

export const light = {
  background: palette.primaryBackground, surface: palette.white, surfaceMuted: palette.lightContainer,
  text: palette.textPrimary, textMuted: palette.textSecondary, textOnPrimary: palette.textWhite,
  border: palette.borderPrimary, icon: palette.iconPrimary,
  primary: palette.buttonPrimary, link: palette.primaryStrong,
  buttonSecondary: palette.buttonSecondary, buttonDisabled: palette.buttonDisabled, buttonDisabledText: palette.textSecondary,
  highlight: palette.secondary, onHighlight: palette.textPrimary, focusRing: palette.accent,
  errorText: palette.error,
  ...status,
};

export const dark: typeof light = {
  background: palette.darkPage, surface: '#2A2A2A', surfaceMuted: '#FFFFFF0D',
  text: palette.textDarkPrimary, textMuted: palette.textDarkSecondary, textOnPrimary: palette.textWhite,
  border: palette.borderSecondary, icon: palette.darkGrey,
  primary: palette.primary, link: palette.accent,
  buttonSecondary: palette.buttonSecondary, buttonDisabled: '#FFFFFF1F', buttonDisabledText: palette.textDarkSecondary,
  highlight: palette.secondary, onHighlight: palette.textPrimary, focusRing: palette.accent,
  errorText: '#FF8A80',
  ...status,
};

export type Theme = typeof light;
