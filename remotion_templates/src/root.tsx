import React from 'react';
import {Composition} from 'remotion';
import {
  BarChart,
  BrollOverlay,
  EndCard,
  FlowDiagram,
  IntroCard,
  LineChart,
  ReactionCard,
  SceneTransition,
  SplitComparison,
  StatExplosion,
  StatReveal,
  TextBurst,
  ThumbnailFrame,
} from './templates';

const fps = 30;
const duration = (props: {durationSec?: number}, fallback: number) =>
  Math.max(1, Math.round((props.durationSec ?? fallback) * fps));

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="FlowDiagram"
        component={FlowDiagram}
        width={1920}
        height={1080}
        fps={fps}
        durationInFrames={135}
        calculateMetadata={({props}) => ({durationInFrames: duration(props, 4.5)})}
      />
      <Composition
        id="StatExplosion"
        component={StatExplosion}
        width={1920}
        height={1080}
        fps={fps}
        durationInFrames={90}
        calculateMetadata={({props}) => ({durationInFrames: duration(props, 3)})}
      />
      <Composition
        id="TextBurst"
        component={TextBurst}
        width={1920}
        height={1080}
        fps={fps}
        durationInFrames={90}
        calculateMetadata={({props}) => ({durationInFrames: duration(props, 3)})}
      />
      <Composition
        id="ReactionCard"
        component={ReactionCard}
        width={1920}
        height={1080}
        fps={fps}
        durationInFrames={90}
        calculateMetadata={({props}) => ({durationInFrames: duration(props, 3)})}
      />
      <Composition
        id="SplitComparison"
        component={SplitComparison}
        width={1920}
        height={1080}
        fps={fps}
        durationInFrames={90}
        calculateMetadata={({props}) => ({durationInFrames: duration(props, 3)})}
      />
      <Composition
        id="StatReveal"
        component={StatReveal}
        width={1920}
        height={1080}
        fps={fps}
        durationInFrames={180}
        calculateMetadata={({props}) => ({durationInFrames: duration(props, 6)})}
      />
      <Composition
        id="BarChart"
        component={BarChart}
        width={1920}
        height={1080}
        fps={fps}
        durationInFrames={240}
        calculateMetadata={({props}) => ({durationInFrames: duration(props, 8)})}
      />
      <Composition
        id="LineChart"
        component={LineChart}
        width={1920}
        height={1080}
        fps={fps}
        durationInFrames={240}
        calculateMetadata={({props}) => ({durationInFrames: duration(props, 8)})}
      />
      <Composition
        id="BrollOverlay"
        component={BrollOverlay}
        width={1920}
        height={1080}
        fps={fps}
        durationInFrames={240}
        calculateMetadata={({props}) => ({durationInFrames: duration(props, 8)})}
      />
      <Composition
        id="SceneTransition"
        component={SceneTransition}
        width={1920}
        height={1080}
        fps={fps}
        durationInFrames={15}
        calculateMetadata={({props}) => ({durationInFrames: duration(props, 0.5)})}
      />
      <Composition
        id="IntroCard"
        component={IntroCard}
        width={1920}
        height={1080}
        fps={fps}
        durationInFrames={90}
        calculateMetadata={({props}) => ({durationInFrames: duration(props, 3)})}
      />
      <Composition
        id="EndCard"
        component={EndCard}
        width={1920}
        height={1080}
        fps={fps}
        durationInFrames={150}
        calculateMetadata={({props}) => ({durationInFrames: duration(props, 5)})}
      />
      <Composition
        id="ThumbnailFrame"
        component={ThumbnailFrame}
        width={1280}
        height={720}
        fps={fps}
        durationInFrames={1}
      />
    </>
  );
};
